import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.payments import schemas
from app.modules.payments.models import DirectDebitBinding, Order, OrderStatus, PaymentStatus, PaymentWebhookEvent
from app.modules.payments.repository import PaymentRepository
from app.modules.events.models import Event
from app.modules.participants.models import ParticipantProfile
from app.modules.iwbif.models import DelegatePackage, DelegateRegistrationDetail
from app.modules.users.models import User
from app.core.config import get_settings
from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.modules.payments.doku import DokuCheckoutClient, verify_signature
from app.modules.payments.doku_snap import DokuSnapClient, ensure_fresh_timestamp, issue_merchant_token, verify_asymmetric_signature, verify_merchant_token, verify_symmetric_signature
from app.modules.registrations.models import Registration, RegistrationStatus


class PaymentService:
    @staticmethod
    async def create_doku_qris(session: AsyncSession, payload: schemas.CreateDokuQrisRequest, user_id: uuid.UUID) -> schemas.DokuQrisResponse:
        registrations = await PaymentRepository.get_registrations_for_user(session, user_id)
        registration = next((row for row in registrations if row.id == payload.registration_id), None)
        if not registration:
            raise NotFoundException("REGISTRATION_NOT_FOUND", "Registrasi tidak ditemukan untuk akun ini")
        order = await PaymentRepository.get_latest_order(session, registration.id)
        if order and order.status == OrderStatus.PAID:
            raise ConflictException("ORDER_ALREADY_PAID", "Registrasi ini sudah dibayar")
        if not order or order.status not in {OrderStatus.PENDING, OrderStatus.DRAFT}:
            order = await PaymentRepository.create_order(session, registration.id)
        if order.currency.upper() != "IDR":
            raise ValidationException("DOKU_IDR_REQUIRED", "QRIS hanya menerima tagihan IDR")
        payment = await PaymentRepository.get_payment_by_order(session, order.id)
        if payment and payment.provider not in {"doku", "doku_snap_qris"}:
            raise ConflictException("LEGACY_PAYMENT_PENDING", "Batalkan transaksi gateway lama terlebih dahulu")
        reference = f"QR{uuid.uuid4().hex[:20].upper()}"
        body = {"partnerReferenceNo": reference, "amount": {"value": str(order.total_amount), "currency": "IDR"}, "additionalInfo": {"feeType": "1"}}
        if order.expires_at:
            body["validityPeriod"] = order.expires_at.astimezone().isoformat(timespec="seconds")
        response, external_id = await DokuSnapClient().create_qris(body)
        qr_content = str(response.get("qrContent") or "")
        if not qr_content:
            raise ValidationException("DOKU_QRIS_CONTENT_MISSING", "DOKU tidak mengembalikan konten QRIS")
        from app.modules.payments.models import Payment
        if not payment:
            payment = Payment(order_id=order.id, provider="doku_snap_qris", gross_amount=order.total_amount, currency=order.currency)
            session.add(payment)
        payment.provider, payment.provider_order_id, payment.payment_type, payment.channel_code = "doku_snap_qris", reference, "doku_snap_qris", "QRIS"
        payment.external_id, payment.provider_reference_no, payment.payment_instructions_url = external_id, response.get("referenceNo"), qr_content
        payment.raw_response, payment.transaction_status = json.dumps(response), PaymentStatus.PENDING
        await session.commit()
        await session.refresh(payment)
        return schemas.DokuQrisResponse(payment_id=payment.id, order_id=order.id, order_number=order.order_number, status=payment.transaction_status, qr_content=qr_content, amount=float(order.total_amount), currency=order.currency, expires_at=order.expires_at)

    @staticmethod
    async def create_doku_direct_debit_binding(session: AsyncSession, payload: schemas.CreateDirectDebitBindingRequest, user_id: uuid.UUID) -> schemas.DirectDebitBindingResponse:
        registrations = await PaymentRepository.get_registrations_for_user(session, user_id)
        registration = next((row for row in registrations if row.id == payload.registration_id), None)
        if not registration:
            raise NotFoundException("REGISTRATION_NOT_FOUND", "Registrasi tidak ditemukan untuk akun ini")
        channel_code = payload.channel_code.strip().upper()
        client = DokuSnapClient()
        channel = client.direct_debit_channels().get(channel_code)
        if not channel:
            raise ValidationException("DOKU_DIRECT_DEBIT_CHANNEL_NOT_CONFIGURED", f"Direct Debit {channel_code} belum dikonfigurasi")
        customer_reference = f"B{uuid.uuid4().hex[:11].upper()}"
        body: dict[str, Any] = {
            "partnerReferenceNo": customer_reference,
            "phoneNo": payload.phone_no,
            "additionalInfo": {
                "channel": channel.get("channel") or f"DIRECT_DEBIT_{channel_code}_SNAP",
                "custIdMerchant": str(registration.participant_id),
            },
        }
        if payload.device_id:
            body["deviceId"] = payload.device_id
        response, _external_id = await client.direct_debit_request(channel_code, "/direct-debit/core/v1/registration-account-binding", body)
        additional = response.get("additionalInfo") or {}
        token = additional.get("bankCardToken") or additional.get("tokenId")
        binding = DirectDebitBinding(
            participant_id=registration.participant_id,
            channel_code=channel_code,
            customer_reference=customer_reference,
            provider_reference_no=response.get("referenceNo"),
            token_id=token,
            status=str(additional.get("status") or "pending").lower(),
            raw_response=json.dumps(response),
        )
        session.add(binding)
        await session.commit()
        await session.refresh(binding)
        return schemas.DirectDebitBindingResponse(binding_id=binding.id, channel_code=channel_code, status=binding.status, redirect_url=response.get("redirectUrl") or response.get("webRedirectUrl"))

    @staticmethod
    async def create_doku_direct_debit_payment(session: AsyncSession, payload: schemas.CreateDirectDebitPaymentRequest, user_id: uuid.UUID) -> schemas.DirectDebitPaymentResponse:
        bindings = await PaymentRepository.get_direct_debit_binding_for_user(session, payload.binding_id, user_id)
        if not bindings or not bindings.token_id:
            raise ValidationException("DOKU_DIRECT_DEBIT_BINDING_REQUIRED", "Binding Direct Debit aktif tidak ditemukan")
        registrations = await PaymentRepository.get_registrations_for_user(session, user_id)
        registration = next((row for row in registrations if row.id == payload.registration_id and row.participant_id == bindings.participant_id), None)
        if not registration:
            raise NotFoundException("REGISTRATION_NOT_FOUND", "Registrasi tidak ditemukan untuk binding ini")
        order = await PaymentRepository.get_latest_order(session, registration.id)
        if order and order.status == OrderStatus.PAID:
            raise ConflictException("ORDER_ALREADY_PAID", "Registrasi ini sudah dibayar")
        if not order or order.status not in {OrderStatus.PENDING, OrderStatus.DRAFT}:
            order = await PaymentRepository.create_order(session, registration.id)
        if order.currency.upper() != "IDR":
            raise ValidationException("DOKU_IDR_REQUIRED", "Direct Debit hanya menerima tagihan IDR")
        payment = await PaymentRepository.get_payment_by_order(session, order.id)
        if payment and payment.provider not in {"doku", "doku_snap_direct_debit"}:
            raise ConflictException("LEGACY_PAYMENT_PENDING", "Batalkan transaksi gateway lama terlebih dahulu")
        reference = f"DD{uuid.uuid4().hex[:10].upper()}"
        if not payment:
            from app.modules.payments.models import Payment
            payment = Payment(order_id=order.id, provider="doku_snap_direct_debit", provider_order_id=reference, payment_type="doku_snap_direct_debit", channel_code=bindings.channel_code, gross_amount=order.total_amount, currency=order.currency, transaction_status=PaymentStatus.PENDING)
            session.add(payment)
        else:
            payment.provider, payment.provider_order_id, payment.payment_type, payment.channel_code, payment.transaction_status = "doku_snap_direct_debit", reference, "doku_snap_direct_debit", bindings.channel_code, PaymentStatus.PENDING
        await session.flush()
        channel = DokuSnapClient().direct_debit_channels().get(bindings.channel_code)
        body = {"partnerReferenceNo": reference, "amount": {"value": str(order.total_amount), "currency": "IDR"}, "additionalInfo": {"channel": (channel or {}).get("channel") or f"DIRECT_DEBIT_{bindings.channel_code}_SNAP", "remarks": f"IWBIF {registration.registration_number}"}}
        response, external_id = await DokuSnapClient().direct_debit_request(bindings.channel_code, "/direct-debit/core/v1/debit/payment-host-to-host", body, customer_token=bindings.token_id)
        payment.external_id, payment.provider_reference_no, payment.checkout_url, payment.raw_response = external_id, response.get("referenceNo"), response.get("webRedirectUrl") or response.get("redirectUrl"), json.dumps(response)
        await session.commit()
        return schemas.DirectDebitPaymentResponse(payment_id=payment.id, order_id=order.id, partner_reference_no=reference, status=payment.transaction_status, redirect_url=payment.checkout_url)

    @staticmethod
    async def verify_doku_direct_debit_otp(session: AsyncSession, payment_id: uuid.UUID, payload: schemas.VerifyDirectDebitOtpRequest, user_id: uuid.UUID) -> dict[str, Any]:
        payment = await PaymentRepository.get_payment_for_user(session, payment_id, user_id)
        binding = await PaymentRepository.get_direct_debit_binding_for_user(session, payload.binding_id, user_id)
        if not payment or payment.provider != "doku_snap_direct_debit" or not binding or not binding.token_id:
            raise NotFoundException("DOKU_DIRECT_DEBIT_PAYMENT_NOT_FOUND", "Pembayaran atau binding Direct Debit tidak ditemukan")
        if payment.channel_code != binding.channel_code or not payment.provider_order_id:
            raise ValidationException("DOKU_DIRECT_DEBIT_BINDING_MISMATCH", "Binding tidak sesuai dengan pembayaran")
        if not payload.otp.isdigit() or len(payload.otp) != 6:
            raise ValidationException("DOKU_DIRECT_DEBIT_INVALID_OTP", "OTP harus terdiri dari 6 digit")
        channel = DokuSnapClient().direct_debit_channels().get(binding.channel_code) or {}
        body = {"originalPartnerReferenceNo": payment.provider_order_id, "otp": payload.otp, "action": "otpPayment", "additionalInfo": {"channel": channel.get("channel") or f"DIRECT_DEBIT_{binding.channel_code}_SNAP", "bankCardToken": binding.token_id}}
        response, external_id = await DokuSnapClient().direct_debit_request(binding.channel_code, "/direct-debit/core/v1/otp-verification", body, customer_token=binding.token_id)
        payment.external_id, payment.raw_response = external_id, json.dumps(response)
        await session.commit()
        return response
    @staticmethod
    async def create_doku_direct_va(session: AsyncSession, payload: schemas.CreateDokuDirectVARequest, user_id: uuid.UUID) -> schemas.DokuDirectVAResponse:
        registrations = await PaymentRepository.get_registrations_for_user(session, user_id)
        registration = next((row for row in registrations if row.id == payload.registration_id), None)
        if not registration:
            raise NotFoundException("REGISTRATION_NOT_FOUND", "Registrasi tidak ditemukan untuk akun ini")
        order = await PaymentRepository.get_latest_order(session, registration.id)
        if order and order.status == OrderStatus.PAID:
            raise ConflictException("ORDER_ALREADY_PAID", "Registrasi ini sudah dibayar")
        if not order or order.status not in {OrderStatus.PENDING, OrderStatus.DRAFT}:
            order = await PaymentRepository.create_order(session, registration.id)
        if order.currency.upper() != "IDR":
            raise ValidationException("DOKU_IDR_REQUIRED", "DOKU Direct VA hanya menerima tagihan IDR; atur harga pembayaran paket dalam IDR")
        payment = await PaymentRepository.get_payment_by_order(session, order.id)
        bank_code = payload.bank_code.strip().upper()
        if payment and payment.payment_type == "doku_snap_va" and payment.channel_code == bank_code and payment.virtual_account_no:
            return schemas.DokuDirectVAResponse(payment_id=payment.id, order_id=order.id, order_number=order.order_number, status=payment.transaction_status, bank_code=bank_code, virtual_account_no=payment.virtual_account_no, amount=float(payment.gross_amount), currency=payment.currency, expires_at=payment.expired_at, instructions_url=payment.payment_instructions_url)
        if payment and payment.transaction_status in {PaymentStatus.CREATED, PaymentStatus.PENDING}:
            raise ConflictException("PAYMENT_CHANNEL_ALREADY_SELECTED", "Order memiliki transaksi aktif; gunakan atau batalkan transaksi tersebut")
        if not payment:
            payment = await PaymentRepository.create_doku_payment(session, order)

        participant = await session.get(ParticipantProfile, registration.participant_id)
        user = await session.get(User, participant.user_id) if participant else None
        if not participant or not user:
            raise ValidationException("PAYMENT_DATA_INCOMPLETE", "Data peserta pembayaran tidak lengkap")
        amount = Decimal(str(order.total_amount)).quantize(Decimal("0.01"))
        expires_at = order.expires_at or datetime.now(timezone.utc)
        request_payload = {
            "customerNo": "0",
            "virtualAccountNo": "",
            "virtualAccountName": participant.full_name[:255],
            "virtualAccountEmail": user.email,
            "virtualAccountPhone": user.phone or "",
            "trxId": order.order_number,
            "totalAmount": {"value": f"{amount:.2f}", "currency": "IDR"},
            "virtualAccountTrxType": "C",
            "expiredDate": expires_at.astimezone().isoformat(timespec="seconds"),
            "additionalInfo": {"channel": f"VIRTUAL_ACCOUNT_{bank_code}"},
        }
        response, external_id = await DokuSnapClient().create_va(bank_code, request_payload)
        va = response.get("virtualAccountData", {})
        va_no = str(va.get("virtualAccountNo") or "").strip()
        if not va_no:
            raise ValidationException("DOKU_VA_NUMBER_MISSING", "DOKU tidak mengembalikan nomor Virtual Account")
        additional = va.get("additionalInfo") or {}
        payment.provider = "doku"
        payment.payment_type = "doku_snap_va"
        payment.channel_code = bank_code
        payment.virtual_account_no = va_no
        payment.provider_transaction_id = external_id
        payment.provider_reference_no = str(va.get("trxId") or response.get("referenceNo") or "") or None
        payment.provider_order_id = order.order_number
        payment.external_id = external_id
        payment.payment_instructions_url = additional.get("howToPayPage")
        payment.raw_response = json.dumps(response)
        payment.transaction_status = PaymentStatus.PENDING
        payment.expired_at = order.expires_at
        order.status = OrderStatus.PENDING
        await session.commit()
        await session.refresh(payment)
        return schemas.DokuDirectVAResponse(payment_id=payment.id, order_id=order.id, order_number=order.order_number, status=payment.transaction_status, bank_code=bank_code, virtual_account_no=va_no, amount=float(payment.gross_amount), currency=payment.currency, expires_at=payment.expired_at, instructions_url=payment.payment_instructions_url)

    @staticmethod
    def issue_doku_snap_token(body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        settings = get_settings()
        client_key = headers.get("x-client-key", "")
        timestamp = headers.get("x-timestamp", "")
        signature = headers.get("x-signature", "")
        expected_client = settings.DOKU_SNAP_DOKU_CLIENT_ID
        if body.get("grantType") != "client_credentials" or not all((client_key, timestamp, signature)):
            raise ValidationException("DOKU_SNAP_INVALID_TOKEN_REQUEST", "Permintaan token B2B tidak valid")
        if expected_client and client_key != expected_client:
            raise ValidationException("DOKU_SNAP_UNKNOWN_CLIENT", "X-CLIENT-KEY DOKU tidak dikenal")
        ensure_fresh_timestamp(timestamp)
        if not verify_asymmetric_signature(signature, client_key, timestamp, settings.DOKU_SNAP_DOKU_PUBLIC_KEY_PATH):
            raise ValidationException("DOKU_SNAP_INVALID_SIGNATURE", "Signature token B2B DOKU tidak valid")
        token, ttl = issue_merchant_token(client_key)
        return {"responseCode": "2007300", "responseMessage": "Successful", "accessToken": token, "tokenType": "Bearer", "expiresIn": ttl, "additionalInfo": {}}

    @staticmethod
    async def handle_doku_snap_va_notification(session: AsyncSession, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        settings = get_settings()
        timestamp = headers.get("x-timestamp", "")
        signature = headers.get("x-signature", "")
        external_id = headers.get("x-external-id", "")
        authorization = headers.get("authorization", "")
        partner_id = headers.get("x-partner-id", "")
        if not all((timestamp, signature, external_id, authorization, partner_id)) or not authorization.startswith("Bearer "):
            raise ValidationException("DOKU_SNAP_INVALID_HEADERS", "Header notification SNAP tidak lengkap")
        if settings.DOKU_SNAP_DOKU_CLIENT_ID and partner_id != settings.DOKU_SNAP_DOKU_CLIENT_ID:
            raise ValidationException("DOKU_SNAP_UNKNOWN_PARTNER", "X-PARTNER-ID notification tidak dikenal")
        ensure_fresh_timestamp(timestamp)
        token = authorization[7:]
        if not verify_merchant_token(token):
            raise ValidationException("DOKU_SNAP_INVALID_TOKEN", "Bearer token notification tidak valid")
        if not verify_symmetric_signature(signature, "POST", settings.DOKU_SNAP_VA_NOTIFICATION_PATH, token, payload, timestamp, settings.DOKU_SNAP_CLIENT_SECRET):
            raise ValidationException("DOKU_SNAP_INVALID_SIGNATURE", "X-SIGNATURE notification tidak valid")

        va_no = str(payload.get("virtualAccountNo") or "").strip()
        trx_id = str(payload.get("trxId") or "")
        paid = payload.get("paidAmount") or {}
        if not va_no or not trx_id or paid.get("value") is None or paid.get("currency") != "IDR":
            raise ValidationException("DOKU_SNAP_INVALID_PAYLOAD", "Payload pembayaran VA SNAP tidak valid")
        payment = await PaymentRepository.get_payment_by_va(session, va_no, lock=True)
        if not payment or payment.provider_order_id != trx_id:
            raise NotFoundException("DOKU_SNAP_PAYMENT_NOT_FOUND", "Transaksi Virtual Account tidak ditemukan")
        order = await session.get(Order, payment.order_id, with_for_update=True)
        if not order:
            raise NotFoundException("DOKU_ORDER_NOT_FOUND", "Order tidak ditemukan")
        if Decimal(str(paid["value"])) != Decimal(str(order.total_amount)):
            raise ValidationException("DOKU_AMOUNT_MISMATCH", "Nominal pembayaran tidak sesuai order")
        provider = "doku_snap_va"
        duplicate = await PaymentRepository.get_webhook_event(session, external_id, provider)
        if not duplicate:
            order.status = OrderStatus.PAID
            payment.transaction_status = PaymentStatus.SUCCESS
            payment.paid_at = datetime.now(timezone.utc)
            payment.raw_response = json.dumps(payload)
            registration = await session.get(Registration, order.registration_id, with_for_update=True)
            if registration and registration.status != RegistrationStatus.CONFIRMED:
                registration.status = RegistrationStatus.PAID
            session.add(PaymentWebhookEvent(payment_id=payment.id, provider=provider, request_id=external_id, event_status="SUCCESS", payload=payload))
            await session.commit()
        return {"responseCode": "2002500", "responseMessage": "Successful", "virtualAccountData": {"partnerServiceId": payload.get("partnerServiceId"), "customerNo": payload.get("customerNo"), "virtualAccountNo": payload.get("virtualAccountNo"), "virtualAccountName": payload.get("virtualAccountName"), "trxId": payload.get("trxId"), "paymentRequestId": payload.get("paymentRequestId"), "paidAmount": payload.get("paidAmount")}}

    @staticmethod
    async def handle_doku_snap_direct_debit_notification(session: AsyncSession, payload: dict[str, Any], headers: dict[str, str], *, e_wallet: bool = False) -> dict[str, Any]:
        settings = get_settings()
        timestamp, signature = headers.get("x-timestamp", ""), headers.get("x-signature", "")
        external_id, authorization = headers.get("x-external-id", ""), headers.get("authorization", "")
        if not all((timestamp, signature, external_id, authorization)) or not authorization.startswith("Bearer "):
            raise ValidationException("DOKU_SNAP_INVALID_HEADERS", "Header notification Direct Debit tidak lengkap")
        ensure_fresh_timestamp(timestamp)
        token = authorization[7:]
        if not verify_merchant_token(token):
            raise ValidationException("DOKU_SNAP_INVALID_TOKEN", "Bearer token notification tidak valid")
        additional = payload.get("additionalInfo") or {}
        channel_value = str(additional.get("channel") or payload.get("channel") or "").upper()
        client = DokuSnapClient()
        channels = client.e_wallet_channels() if e_wallet else client.direct_debit_channels()
        channel_key, config = next(((key, item) for key, item in channels.items() if str(item.get("channel") or "").upper() == channel_value), (None, None))
        if not config:
            raise ValidationException("DOKU_DIRECT_DEBIT_UNKNOWN_CHANNEL", "Channel Direct Debit notification tidak dikonfigurasi")
        secret = str(config.get("consumer_secret") or settings.DOKU_SNAP_CLIENT_SECRET)
        notification_path = settings.DOKU_SNAP_EWALLET_NOTIFICATION_PATH if e_wallet else settings.DOKU_SNAP_DIRECT_DEBIT_NOTIFICATION_PATH
        if not secret or not verify_symmetric_signature(signature, "POST", notification_path, token, payload, timestamp, secret):
            raise ValidationException("DOKU_SNAP_INVALID_SIGNATURE", "Signature notification pembayaran tidak valid")
        reference = str(payload.get("partnerReferenceNo") or payload.get("originalPartnerReferenceNo") or "")
        if not reference:
            raise ValidationException("DOKU_SNAP_INVALID_PAYLOAD", "partnerReferenceNo wajib ada")
        payment = await PaymentRepository.get_payment_by_provider_order_id(session, reference, lock=True)
        if not payment:
            raise NotFoundException("DOKU_SNAP_PAYMENT_NOT_FOUND", "Pembayaran Direct Debit tidak ditemukan")
        order = await session.get(Order, payment.order_id, with_for_update=True)
        if not order:
            raise NotFoundException("DOKU_ORDER_NOT_FOUND", "Order tidak ditemukan")
        amount = payload.get("amount") or payload.get("paidAmount") or {}
        if amount.get("value") is not None and Decimal(str(amount["value"])) != Decimal(str(order.total_amount)):
            raise ValidationException("DOKU_AMOUNT_MISMATCH", "Nominal pembayaran Direct Debit tidak sesuai order")
        status = str(payload.get("latestTransactionStatus") or payload.get("transactionStatus") or payload.get("status") or "SUCCESS").upper()
        provider = "doku_snap_e_wallet" if e_wallet else "doku_snap_direct_debit"
        if not await PaymentRepository.get_webhook_event(session, external_id, provider):
            if status in {"SUCCESS", "PAID", "00"}:
                order.status, payment.transaction_status, payment.paid_at = OrderStatus.PAID, PaymentStatus.SUCCESS, datetime.now(timezone.utc)
                registration = await session.get(Registration, order.registration_id, with_for_update=True)
                if registration and registration.status != RegistrationStatus.CONFIRMED:
                    registration.status = RegistrationStatus.PAID
            elif status in {"FAILED", "CANCELLED", "CANCELED"}:
                order.status, payment.transaction_status = OrderStatus.CANCELED, PaymentStatus.FAILED
            payment.channel_code = channel_value or channel_key
            payment.raw_response = json.dumps(payload)
            session.add(PaymentWebhookEvent(payment_id=payment.id, provider=provider, request_id=external_id, event_status=status, payload=payload))
            await session.commit()
        return {"responseCode": "2005400", "responseMessage": "Successful", "partnerReferenceNo": reference, "additionalInfo": {}}
    @staticmethod
    async def create_doku_checkout(
        session: AsyncSession,
        payload: schemas.CreateDokuCheckoutRequest,
        user_id: uuid.UUID,
    ) -> tuple[schemas.DokuCheckoutResponse, Order]:
        registrations = await PaymentRepository.get_registrations_for_user(session, user_id)
        registration = None
        if payload.order_id is not None:
            latest_order = await PaymentRepository.get_order_for_user(session, payload.order_id, user_id)
            if latest_order is None:
                raise NotFoundException("ORDER_NOT_FOUND", "Order tidak ditemukan untuk akun ini")
            if latest_order.status == OrderStatus.PAID:
                latest_payment = await PaymentRepository.get_payment_by_order(session, latest_order.id)
                return schemas.DokuCheckoutResponse(payment_url="", already_paid=True, payment_id=latest_payment.id if latest_payment else None, order_status=latest_order.status, requires_payment=False), latest_order
            if latest_order.status not in {OrderStatus.PENDING, OrderStatus.DRAFT}:
                raise ConflictException("ORDER_NOT_PAYABLE", "Order tidak dapat dibayar")
            payment = await PaymentRepository.get_payment_by_order(session, latest_order.id)
        else:
            latest_order = None
            payment = None
        if payload.registration_id is not None:
            registration = next(
                (reg for reg in registrations if reg.id == payload.registration_id),
                None,
            )
            if registration is None:
                raise ValidationException(
                    code="REGISTRATION_NOT_OWNED",
                    message="Registrasi tidak ditemukan untuk akun ini",
                )
        elif payload.order_id is None:
            payable = [
                reg for reg in registrations
                if getattr(reg.status, "value", reg.status) in {"awaiting_payment", "payment_pending", "verified", "draft"}
            ]
            registration = payable[0] if payable else (registrations[0] if registrations else None)

        if registration is None and payload.order_id is None:
            raise NotFoundException(
                code="REGISTRATION_NOT_FOUND",
                message="Tidak ada registrasi untuk akun ini",
            )

        if payload.order_id is None:
            latest_order = await PaymentRepository.get_latest_order(session, registration.id)
        if latest_order and latest_order.status == OrderStatus.PAID:
            latest_payment = await PaymentRepository.get_payment_by_order(session, latest_order.id)
            payment_id = latest_payment.id if latest_payment else None
            return (
                schemas.DokuCheckoutResponse(
                    payment_url="",
                    already_paid=True,
                    payment_id=payment_id,
                    order_status=latest_order.status,
                    requires_payment=False,
                ),
                latest_order,
            )

        if latest_order and latest_order.status in [OrderStatus.PENDING, OrderStatus.DRAFT]:
            payment = payment or await PaymentRepository.get_payment_by_order(session, latest_order.id)
            if not payment:
                payment = await PaymentRepository.create_doku_payment(session, latest_order)
            if payment.provider == "doku" and payment.checkout_url:
                return (schemas.DokuCheckoutResponse(payment_url=payment.checkout_url, expires_at=payment.expired_at, already_paid=False, payment_id=payment.id, order_status=latest_order.status, requires_payment=True), latest_order)
            # A pending legacy provider transaction must not be silently reused.
            if payment.provider != "doku":
                raise ConflictException("LEGACY_PAYMENT_PENDING", "Batalkan transaksi payment gateway lama sebelum membuat DOKU Checkout")
        else:
            latest_order = await PaymentRepository.create_order(session, registration.id)
            payment = await PaymentRepository.create_doku_payment(session, latest_order)

        participant = await session.get(ParticipantProfile, registration.participant_id) if registration else None
        user = await session.get(User, participant.user_id) if participant else await session.get(User, user_id)
        event = await session.get(Event, registration.event_id) if registration else None
        if event is None:
            from app.modules.store.models import Product, OrderItem
            event_id = (await session.execute(select(Product.event_id).join(OrderItem, OrderItem.product_id == Product.id).where(OrderItem.order_id == latest_order.id).limit(1))).scalar_one_or_none()
            event = await session.get(Event, event_id) if event_id else None
        if not user or not event:
            raise ValidationException("PAYMENT_DATA_INCOMPLETE", "Data user atau event tidak lengkap")
        customer_name = participant.full_name if participant else (user.full_name or user.email)
        customer_id = str(participant.id) if participant else str(user.id)
        from app.modules.store.models import OrderItem
        order_items = list((await session.execute(select(OrderItem).where(OrderItem.order_id == latest_order.id))).scalars())
        amount = float(latest_order.total_amount)
        if amount.is_integer(): amount = int(amount)
        request_body = {
            "order": {
                "amount": amount,
                "invoice_number": latest_order.order_number,
                "currency": latest_order.currency,
                "callback_url": get_settings().DOKU_CALLBACK_URL,
                "auto_redirect": True,
                "line_items": ([{"name": item.product_name, "price": float(item.unit_price), "quantity": item.quantity} for item in order_items] or [{"name": f"IWBIF 2026 - {registration.registration_number if registration else latest_order.order_number}", "price": amount, "quantity": 1}]),
            },
            "payment": {"payment_due_date": get_settings().DOKU_PAYMENT_DUE_MINUTES},
            "customer": {"id": customer_id, "name": customer_name, "email": user.email, "phone": user.phone or ""},
            "additional_info": {"event_id": str(event.id), "registration_id": str(registration.id) if registration else "", "order_id": str(latest_order.id)},
        }
        response, request_id = await DokuCheckoutClient().create_payment(request_body)
        response_payment = response.get("response", {}).get("payment", response.get("payment", {}))
        payment_url = response_payment.get("url")
        if not payment_url:
            raise ValidationException("DOKU_PAYMENT_URL_MISSING", "DOKU tidak mengembalikan payment URL")
        payment.provider = "doku"
        payment.provider_transaction_id = request_id
        payment.provider_order_id = latest_order.order_number
        payment.checkout_url = payment_url
        payment.raw_response = json.dumps(response)
        payment.transaction_status = PaymentStatus.PENDING
        payment.expired_at = latest_order.expires_at
        await session.commit(); await session.refresh(payment)
        return (
            schemas.DokuCheckoutResponse(
                payment_url=payment_url,
                token=response_payment.get("token_id"),
                expires_at=payment.expired_at,
                already_paid=False,
                payment_id=payment.id,
                order_status=latest_order.status,
                requires_payment=True,
            ), latest_order,
        )

    @staticmethod
    async def get_payment(session: AsyncSession, payment_id: uuid.UUID, user_id: uuid.UUID):
        payment = await PaymentRepository.get_payment_for_user(session, payment_id, user_id)
        if not payment:
            from app.core.exceptions import NotFoundException

            raise NotFoundException(code="PAYMENT_NOT_FOUND", message="Payment tidak ditemukan")
        return payment

    @staticmethod
    async def get_order(session: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID):
        order = await PaymentRepository.get_order_for_user(session, order_id, user_id)
        if not order:
            raise NotFoundException("ORDER_NOT_FOUND", "Order tidak ditemukan")
        return order

    @staticmethod
    async def get_invoice(session: AsyncSession, registration_ref: str | uuid.UUID, user_id: uuid.UUID) -> schemas.InvoiceRead:
        reg = await PaymentRepository.get_registration(session, registration_ref)
        participant = await session.get(ParticipantProfile, reg.participant_id)
        if not participant:
            from app.core.exceptions import NotFoundException

            raise NotFoundException(code="PARTICIPANT_NOT_FOUND", message="Profil peserta tidak ditemukan")
        if participant.user_id != user_id:
            raise NotFoundException(code="REGISTRATION_NOT_FOUND", message="Registrasi tidak ditemukan")

        user = await session.get(User, participant.user_id)
        event = await session.get(Event, reg.event_id)
        detail = await session.get(DelegateRegistrationDetail, reg.id)
        package = await session.get(DelegatePackage, detail.delegate_package_id) if detail else None
        order = await PaymentRepository.get_latest_order(session, reg.id)
        payment = None
        if order:
            payment = await PaymentRepository.get_payment_by_order(session, order.id)

        order_data = None
        if order:
            order_data = schemas.OrderRead.model_validate(order)
        payment_data = None
        if payment:
            payment_data = schemas.PaymentRead.model_validate(payment)

        return schemas.InvoiceRead(
            registration=schemas.InvoiceRegistration(
                id=reg.id,
                registration_number=reg.registration_number,
                status=reg.status,
                event_id=reg.event_id,
                event_name=event.name if event else None,
                participant_id=reg.participant_id,
                delegate_package_id=package.id if package else None,
                delegate_package_code=package.code if package else None,
                delegate_package_name=package.name if package else None,
                confirmed_at=reg.confirmed_at,
            ),
            participant=schemas.InvoiceParticipant(
                id=participant.id,
                full_name=participant.full_name,
                organization_name=participant.organization_name,
                email=user.email if user else "",
            ),
            order=order_data,
            payment=payment_data,
        )

    @staticmethod
    async def get_my_invoices(session: AsyncSession, user_id: uuid.UUID, event_id: uuid.UUID | None = None) -> list[schemas.InvoiceRead]:
        registrations = await PaymentRepository.get_registrations_for_user(session, user_id, event_id)
        if not registrations:
            return []

        result: list[schemas.InvoiceRead] = []
        for reg in registrations:
            participant = await session.get(ParticipantProfile, reg.participant_id)
            if not participant:
                continue
            user = await session.get(User, participant.user_id)
            event = await session.get(Event, reg.event_id)
            detail = await session.get(DelegateRegistrationDetail, reg.id)
            package = await session.get(DelegatePackage, detail.delegate_package_id) if detail else None
            order = await PaymentRepository.get_latest_order(session, reg.id)
            payment = await PaymentRepository.get_payment_by_order(session, order.id) if order else None

            registration = schemas.InvoiceRegistration(
                id=reg.id,
                registration_number=reg.registration_number,
                status=reg.status,
                event_id=reg.event_id,
                event_name=event.name if event else None,
                participant_id=reg.participant_id,
                delegate_package_id=package.id if package else None,
                delegate_package_code=package.code if package else None,
                delegate_package_name=package.name if package else None,
                confirmed_at=reg.confirmed_at,
            )
            participant_info = schemas.InvoiceParticipant(
                id=participant.id,
                full_name=participant.full_name,
                organization_name=participant.organization_name,
                email=user.email if user else "",
            )
            result.append(
                schemas.InvoiceRead(
                    registration=registration,
                    participant=participant_info,
                    order=schemas.OrderRead.model_validate(order) if order else None,
                    payment=schemas.PaymentRead.model_validate(payment) if payment else None,
                )
            )
        return result

    @staticmethod
    async def handle_doku_notification(session: AsyncSession, body: bytes, headers: dict[str, str]) -> str:
        settings = get_settings()
        client_id = headers.get("client-id", "")
        request_id = headers.get("request-id", "")
        timestamp = headers.get("request-timestamp", "")
        signature = headers.get("signature", "")
        if not settings.DOKU_CLIENT_ID or not settings.DOKU_SECRET_KEY:
            raise ValidationException("DOKU_NOT_CONFIGURED", "DOKU belum dikonfigurasi")
        if client_id != settings.DOKU_CLIENT_ID or not all((request_id, timestamp, signature)):
            raise ValidationException("DOKU_INVALID_HEADERS", "Header notifikasi DOKU tidak valid")
        if not verify_signature(signature, client_id, request_id, timestamp, settings.DOKU_NOTIFICATION_PATH, body, settings.DOKU_SECRET_KEY):
            raise ValidationException("DOKU_INVALID_SIGNATURE", "Signature notifikasi DOKU tidak valid")
        if await PaymentRepository.get_webhook_event(session, request_id):
            return "already_processed"
        try:
            payload: dict[str, Any] = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationException("DOKU_INVALID_PAYLOAD", "Payload notifikasi DOKU tidak valid") from exc
        order_data = payload.get("order", {})
        transaction = payload.get("transaction", {})
        order_number = order_data.get("invoice_number")
        status = str(transaction.get("status") or payload.get("payment", {}).get("status") or "").upper()
        if not order_number or not status:
            raise ValidationException("DOKU_INVALID_PAYLOAD", "Invoice number dan transaction status wajib ada")
        order = await PaymentRepository.get_order_by_number(session, order_number, lock=True)
        if not order:
            raise NotFoundException("DOKU_ORDER_NOT_FOUND", "Order DOKU tidak ditemukan")
        if await PaymentRepository.get_webhook_event(session, request_id):
            return "already_processed"
        notified_amount = Decimal(str(order_data.get("amount")))
        if notified_amount != Decimal(str(order.total_amount)):
            raise ValidationException("DOKU_AMOUNT_MISMATCH", "Nominal notifikasi DOKU tidak sesuai order")
        payment = await PaymentRepository.get_payment_by_order(session, order.id)
        if not payment or payment.provider != "doku":
            raise NotFoundException("DOKU_PAYMENT_NOT_FOUND", "Payment DOKU tidak ditemukan")
        if status == "SUCCESS":
            order.status = OrderStatus.PAID
            payment.transaction_status = PaymentStatus.SUCCESS
            payment.paid_at = datetime.now(timezone.utc)
            registration = await session.get(Registration, order.registration_id)
            if registration and registration.status != RegistrationStatus.CONFIRMED:
                registration.status = RegistrationStatus.PAID
        elif status in {"FAILED", "CANCELLED", "CANCELED"}:
            order.status = OrderStatus.CANCELED
            payment.transaction_status = PaymentStatus.FAILED
        elif status == "EXPIRED":
            order.status = OrderStatus.EXPIRED
            payment.transaction_status = PaymentStatus.EXPIRED
            payment.expired_at = datetime.now(timezone.utc)
        else:
            payment.transaction_status = status.lower()
        payment.raw_response = json.dumps(payload)
        session.add(PaymentWebhookEvent(payment_id=payment.id, provider="doku", request_id=request_id, event_status=status, payload=payload))
        await session.commit()
        return status.lower()
