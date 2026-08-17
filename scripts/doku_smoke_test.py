"""
DOKU smoke test runner for IWBIF backend.

Usage examples:
  python scripts/doku_smoke_test.py \
    --base-url https://api-event.gagakrimang.web.id \
    --email user@example.com \
    --password your-password \
    --registration-id 00000000-0000-0000-0000-000000000000 \
    --bank-code MANDIRI \
    --run-webhook \
    --output-dir reports
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
import os
import sys
from typing import Any

import requests


def canonical_time() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_success_payload(response: requests.Response, allow_status: set[int] | None = None) -> tuple[dict[str, Any], bool]:
    try:
        data = response.json()
    except ValueError:
        return {"raw": response.text}, False
    if allow_status is None:
        allow_status = {200, 201}
    if response.status_code not in allow_status:
        return data, False
    payload = data.get("data") if isinstance(data, dict) else None
    return (payload if isinstance(payload, dict) else data), True


def generate_legacy_doku_signature(client_id: str, request_id: str, timestamp: str, target: str, body: bytes, secret: str) -> str:
    digest = base64.b64encode(hashlib.sha256(body).digest()).decode("ascii")
    component = (
        f"Client-Id:{client_id}\n"
        f"Request-Id:{request_id}\n"
        f"Request-Timestamp:{timestamp}\n"
        f"Request-Target:{target}\n"
        f"Digest:{digest}"
    )
    sig = hmac.new(secret.encode("utf-8"), component.encode("utf-8"), hashlib.sha256).digest()
    return "HMACSHA256=" + base64.b64encode(sig).decode("ascii")


def generate_snap_signature(method: str, path: str, token: str, payload: dict[str, Any], timestamp: str, secret: str) -> str:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    body_hash = hashlib.sha256(body).hexdigest().lower()
    component = f"{method.upper()}:{path}:{token}:{body_hash}:{timestamp}"
    return base64.b64encode(hmac.new(secret.encode("utf-8"), component.encode("utf-8"), hashlib.sha512).digest()).decode("ascii")


class SmokeTestRunner:
    def __init__(self, base_url: str, email: str, password: str, registration_id: str | None = None, bank_code: str = "MANDIRI",
                 run_webhook: bool = True, run_legacy_webhook: bool = True, run_snap_webhook: bool = True, dry_run: bool = False, output_dir: str = "reports"):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.registration_id = registration_id
        self.bank_code = bank_code.upper()
        self.run_webhook = run_webhook
        self.run_legacy_webhook = run_legacy_webhook
        self.run_snap_webhook = run_snap_webhook
        self.dry_run = dry_run
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.report: dict[str, Any] = {
            "started_at": utc_now_iso(),
            "base_url": self.base_url,
            "steps": [],
            "summary": {},
        }
        self.auth_token: str | None = None
        self.settings: dict[str, Any] = {}
        self.payment: dict[str, Any] | None = None
        self.order: dict[str, Any] | None = None

    def _log(self, step: str, ok: bool, detail: Any = None, error: str | None = None) -> None:
        entry = {"step": step, "ok": ok, "detail": detail, "error": error}
        self.report["steps"].append(entry)

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {}) or {}
        if self.auth_token and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return self.session.request(method, url, headers=headers, timeout=60, **kwargs)

    def _load_user_and_settings(self) -> None:
        response = self._request("POST", "/auth/login", json={"email": self.email, "password": self.password})
        data, ok = parse_success_payload(response)
        if not ok or not isinstance(data, dict):
            self._log("login", False, detail={"status_code": response.status_code, "response": data})
            raise RuntimeError("Login failed")
        self.auth_token = data.get("access_token")
        user = data.get("user", {})
        self.report["summary"]["user"] = {
            "id": str(user.get("id", "")),
            "email": user.get("email"),
        }
        self._log("login", True, detail={"user_id": user.get("id")})

    def _ensure_snap_token(self) -> str:
        if self.settings.get("DOKU_SNAP_MOCK_TOKEN"):
            return self.settings["DOKU_SNAP_MOCK_TOKEN"]

        if not (self.settings.get("DOKU_SNAP_PARTNER_ID") and self.settings.get("DOKU_SNAP_PRIVATE_KEY_PATH")):
            raise RuntimeError("Missing DOKU_SNAP_PARTNER_ID or DOKU_SNAP_PRIVATE_KEY_PATH to generate SNAP token")

        try:
            from app.modules.payments.doku_snap import issue_merchant_token  # type: ignore
        except Exception as exc:
            raise RuntimeError("Cannot import backend DOKU SNAP signer for token generation") from exc

        token, _ttl = issue_merchant_token(self.settings["DOKU_SNAP_PARTNER_ID"])
        self.settings["DOKU_SNAP_MOCK_TOKEN"] = token
        return token

    def _fetch_doku_settings(self) -> None:
        # There is no dedicated public endpoint for these settings.
        # We read only non-sensitive URLs from arguments and secrets from environment
        # so the script can simulate webhook signatures from the same operator machine.
        self.settings = {
            "DOKU_CLIENT_ID": os.getenv("DOKU_CLIENT_ID", ""),
            "DOKU_SECRET_KEY": os.getenv("DOKU_SECRET_KEY", ""),
            "DOKU_SNAP_CLIENT_SECRET": os.getenv("DOKU_SNAP_CLIENT_SECRET", ""),
            "DOKU_SNAP_PARTNER_ID": os.getenv("DOKU_SNAP_PARTNER_ID", ""),
            "DOKU_SNAP_DOKU_CLIENT_ID": os.getenv("DOKU_SNAP_DOKU_CLIENT_ID", ""),
            "DOKU_SNAP_VA_NOTIFICATION_PATH": os.getenv("DOKU_SNAP_VA_NOTIFICATION_PATH", "/api/v1/webhooks/doku/snap/va/payment"),
            "DOKU_SNAP_MOCK_TOKEN": os.getenv("DOKU_SNAP_MOCK_TOKEN", ""),
            "DOKU_SNAP_PRIVATE_KEY_PATH": os.getenv("DOKU_SNAP_PRIVATE_KEY_PATH", ""),
        }
        self._log("settings_preflight", True, detail={
            "has_doku_client": bool(self.settings["DOKU_CLIENT_ID"]),
            "has_doku_secret": bool(self.settings["DOKU_SECRET_KEY"]),
            "has_snap_client_secret": bool(self.settings["DOKU_SNAP_CLIENT_SECRET"]),
            "has_snap_partner_id": bool(self.settings["DOKU_SNAP_PARTNER_ID"]),
            "has_snap_private_key": bool(self.settings["DOKU_SNAP_PRIVATE_KEY_PATH"]),
            "has_snap_token": bool(self.settings["DOKU_SNAP_MOCK_TOKEN"]),
        })

    def _pick_registration(self) -> str:
        if self.registration_id:
            return self.registration_id
        response = self._request("GET", "/api/v1/payments/me/invoices")
        data, ok = parse_success_payload(response)
        if not ok or not isinstance(data, list):
            self._log("pick_registration", False, detail={"status_code": response.status_code, "response": data})
            raise RuntimeError("Unable to read invoices for current user")
        if not data:
            self._log("pick_registration", False, detail="No invoices found for user")
            raise RuntimeError("No registration available; provide --registration-id")
        # Prefer non-paid invoice to create new VA against active registration.
        for row in data:
            payment = row.get("payment")
            if payment and str(payment.get("transaction_status", "")).lower() != "success":
                reg_id = str(row["registration"]["id"])
                self._log("pick_registration", True, detail={"registration_id": reg_id, "source": "first_non_success"})
                return reg_id
        reg_id = str(data[0]["registration"]["id"])
        self._log("pick_registration", True, detail={"registration_id": reg_id, "source": "first_any"})
        return reg_id

    def _test_methods(self) -> None:
        response = self._request("GET", "/api/v1/payments/doku/direct/methods")
        data, ok = parse_success_payload(response)
        if not ok:
            self._log("doku_direct_methods", False, detail={"status_code": response.status_code, "response": data})
            raise RuntimeError("Direct methods endpoint failed")
        banks = data.get("virtual_accounts", [])
        has_bank = self.bank_code in banks
        self._log("doku_direct_methods", True, detail={"configured_banks": banks, "bank_code_present": has_bank})
        if not has_bank and banks:
            # auto-fail early to avoid 400 from VA create endpoint
            raise RuntimeError(f"Bank {self.bank_code} not configured in Direct methods")

    def _create_direct_va(self, registration_id: str) -> None:
        if self.dry_run:
            self._log("create_doku_direct_va", True, detail="dry_run=true skipped creation")
            return
        response = self._request(
            "POST",
            "/api/v1/payments/doku/direct/va",
            json={"registration_id": registration_id, "bank_code": self.bank_code},
        )
        data, ok = parse_success_payload(response, allow_status={200, 201})
        if not ok or not isinstance(data, dict):
            self._log("create_doku_direct_va", False, detail={"status_code": response.status_code, "response": data})
            raise RuntimeError("Failed create direct VA")
        self.payment = data
        self._log("create_doku_direct_va", True, detail={"payment_id": str(data.get("payment_id")), "order_id": str(data.get("order_id")), "va": data.get("virtual_account_no")})
        self._refresh_order_and_payment(str(data.get("order_id")), str(data.get("payment_id")))

    def _refresh_order_and_payment(self, order_id: str, payment_id: str) -> None:
        order_resp = self._request("GET", f"/api/v1/payments/{payment_id}")
        order_data, ok1 = parse_success_payload(order_resp)
        if ok1 and isinstance(order_data, dict):
            self._log("get_payment", True, detail={"payment_id": payment_id, "status": order_data.get("transaction_status")})
            self.payment.update(order_data)
        pay_resp = self._request("GET", f"/api/v1/orders/{order_id}")
        pay_data, ok2 = parse_success_payload(pay_resp)
        if ok2 and isinstance(pay_data, dict):
            self.order = pay_data
            self._log("get_order", True, detail={"order_id": order_id, "status": pay_data.get("status"), "total": pay_data.get("total_amount")})
        if not ok1 or not ok2:
            self._log("get_payment_or_order", False, detail={"payment_status": ok1, "order_status": ok2, "payment_resp": order_data, "order_resp": pay_data})

    def _simulate_doku_webhook(self) -> None:
        if not self.payment or not self.order:
            self._log("simulate_legacy_webhook", False, detail="payment/order not available")
            return
        # Reuse settings from backend docs: these must be set in env of test runner
        client_id = self.settings.get("DOKU_CLIENT_ID", "")
        secret = self.settings.get("DOKU_SECRET_KEY", "")
        path = "/api/v1/webhooks/doku"
        if not client_id or not secret:
            self._log("simulate_legacy_webhook", False, detail="Missing DOKU_CLIENT_ID/DOKU_SECRET_KEY from environment")
            return
        payload = {
            "order": {
                "invoice_number": self.order.get("order_number"),
                "amount": self.order.get("total_amount"),
            },
            "transaction": {"status": "SUCCESS"},
            "payment": {"status": "SUCCESS"},
        }
        request_id = str(uuid.uuid4())
        ts = canonical_time()
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        signature = generate_legacy_doku_signature(client_id, request_id, ts, path, body, secret)
        headers = {
            "Client-Id": client_id,
            "Request-Id": request_id,
            "Request-Timestamp": ts,
            "Signature": signature,
            "Content-Type": "application/json",
        }
        response = self._request("POST", path, json=payload, headers=headers)
        data, ok = parse_success_payload(response)
        self._log("simulate_legacy_webhook", ok, detail={"status_code": response.status_code, "response": data})

    def _simulate_snap_webhook(self) -> None:
        if not self.payment or not self.order:
            self._log("simulate_snap_webhook", False, detail="payment/order not available")
            return
        token_secret = self.settings.get("DOKU_SNAP_CLIENT_SECRET", "")
        partner_id = self.settings.get("DOKU_SNAP_PARTNER_ID", "")
        doku_client_id = self.settings.get("DOKU_SNAP_DOKU_CLIENT_ID", "")
        path = self.settings.get("DOKU_SNAP_VA_NOTIFICATION_PATH", "/api/v1/webhooks/doku/snap/va/payment")
        if not token_secret or not partner_id:
            self._log("simulate_snap_webhook", False, detail="Missing DOKU_SNAP_CLIENT_SECRET or DOKU_SNAP_PARTNER_ID in environment")
            return

        # DOKU SNAP notification requires an active merchant token.
        # Generate automatically from local private key + partner id when env token is absent.
        try:
            token = self._ensure_snap_token()
        except Exception as exc:
            self._log("simulate_snap_webhook", False, detail=f"token generation failed: {exc}")
            return

        payload = {
            "virtualAccountNo": self.payment.get("virtual_account_no"),
            "trxId": self.order.get("order_number"),
            "partnerServiceId": self.payment.get("channel_code"),
            "customerNo": "0",
            "virtualAccountName": "Test User",
            "paidAmount": {"value": str(self.order.get("total_amount")), "currency": "IDR"},
            "paymentMethod": "VIRTUAL_ACCOUNT",
            "paymentRequestId": str(self.order.get("order_number")),
        }
        ts = canonical_time()
        signature = generate_snap_signature("POST", path, token, payload, ts, token_secret)
        headers = {
            "x-timestamp": ts,
            "x-signature": signature,
            "x-external-id": str(uuid.uuid4()),
            "authorization": f"Bearer {token}",
            "x-partner-id": doku_client_id or partner_id,
            "Content-Type": "application/json",
        }
        response = self._request("POST", path, json=payload, headers=headers)
        data, ok = parse_success_payload(response)
        self._log("simulate_snap_webhook", ok, detail={"status_code": response.status_code, "response": data})

    def run(self) -> None:
        try:
            self._load_user_and_settings()
            self._test_methods()
            self._fetch_doku_settings()
            registration_id = self._pick_registration()
            self._create_direct_va(registration_id)
            self._refresh_order_and_payment(str(self.payment["order_id"]), str(self.payment["payment_id"]))
            if self.run_webhook:
                if self.run_legacy_webhook:
                    self._simulate_doku_webhook()
                if self.run_snap_webhook:
                    self._simulate_snap_webhook()
            self.report["summary"].update({
                "result": "ok",
                "payment": self.payment,
                "order": self.order,
            })
        except Exception as exc:
            self.report["summary"].update({
                "result": "failed",
                "error": str(exc),
            })
            self._log("fatal", False, error=str(exc))
        finally:
            self.report["finished_at"] = utc_now_iso()
            self._write_report()

    def _write_report(self) -> None:
        out = self.output_dir / f"doku_smoke_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with out.open("w", encoding="utf-8") as f:
            json.dump(self.report, f, ensure_ascii=False, indent=2, default=str)
        self.report["summary"]["report_path"] = str(out)
        print(f"Report written: {out}")

    def print_summary(self) -> None:
        steps_ok = sum(1 for item in self.report.get("steps", []) if item.get("ok") is True)
        steps_total = len(self.report.get("steps", []))
        failed_steps = [item for item in self.report.get("steps", []) if item.get("ok") is False]
        print("== DOKU Smoke Summary ==")
        print(f"base_url: {self.base_url}")
        print(f"result: {self.report.get('summary', {}).get('result')}")
        print(f"steps: {steps_ok}/{steps_total} passed")
        if self.report.get("summary", {}).get("payment"):
            print(f"payment_id: {self.report['summary']['payment'].get('payment_id')}")
        if self.report.get("summary", {}).get("order"):
            print(f"order_id: {self.report['summary']['order'].get('id')}")
        if failed_steps:
            print("failed steps:")
            for item in failed_steps:
                print(f"- {item.get('step')}: {item.get('detail') or item.get('error')}")
        print(f"report: {self.report['summary'].get('report_path')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DOKU production smoke test against FastAPI backend")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--registration-id", help="Registration UUID to create payment against")
    parser.add_argument("--bank-code", default="MANDIRI")
    parser.add_argument("--mode", choices=["full", "snap-only", "legacy-only", "payment-only"], default="full", help="Execution mode")
    parser.add_argument("--run-webhook", action="store_true", default=False, help="Send webhook simulation calls if possible")
    parser.add_argument("--skip-legacy-webhook", action="store_true", help="Skip legacy /api/v1/webhooks/doku simulation")
    parser.add_argument("--skip-snap-webhook", action="store_true", help="Skip /api/v1/webhooks/doku/snap/va/payment simulation")
    parser.add_argument("--assert-on-failure", action="store_true", help="Exit with non-zero if result is failed or required step failed")
    parser.add_argument("--required-steps", default="", help="Comma separated step names that must be ok (example: login,doku_direct_methods,create_doku_direct_va)")
    parser.add_argument("--assert-payment-status", default="", help="Assert payment/order final status must match (supports comma or | delimiter). Example: PENDING,SUCCESS")
    parser.add_argument("--dry-run", action="store_true", help="Only do readiness checks; do not create payment")
    parser.add_argument("--output-dir", default="reports")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    runner = SmokeTestRunner(
        base_url=args.base_url,
        email=args.email,
        password=args.password,
        registration_id=args.registration_id,
        bank_code=args.bank_code,
        run_webhook=args.run_webhook if args.run_webhook else args.mode in {"full", "snap-only", "legacy-only"},
        run_legacy_webhook=not args.skip_legacy_webhook and args.mode in {"full", "legacy-only"},
        run_snap_webhook=not args.skip_snap_webhook and args.mode in {"full", "snap-only"},
        dry_run=args.dry_run,
        output_dir=args.output_dir,
    )
    if args.mode == "payment-only":
        runner.run_webhook = False
    runner.run()
    runner.print_summary()
    if args.assert_on_failure:
        required = [item.strip() for item in args.required_steps.split(",") if item.strip()]
        if required:
            step_index = {item["step"]: item["ok"] for item in runner.report.get("steps", []) if isinstance(item, dict) and "step" in item}
            for step in required:
                if step_index.get(step) is not True:
                    print(f"REQUIRED_STEP_FAILED={step}")
                    sys.exit(2)

    if args.assert_on_failure and args.assert_payment_status:
        normalized_targets = {token.strip().lower() for token in args.assert_payment_status.replace("|", ",").split(",") if token.strip()}
        payment_status = str(runner.report.get("summary", {}).get("payment", {}).get("transaction_status", "")).lower() if runner.report.get("summary", {}).get("payment") else ""
        order_status = str(runner.report.get("summary", {}).get("order", {}).get("status", "")).lower() if runner.report.get("summary", {}).get("order") else ""
        if not ((payment_status and payment_status in normalized_targets) or (order_status and order_status in normalized_targets)):
            print(f"ASSERT_PAYMENT_STATUS_FAILED=payment={payment_status}, order={order_status}, expected_any={sorted(normalized_targets)}")
            sys.exit(3)
        runner.report["summary"]["asserted_statuses"] = sorted(normalized_targets)

    if runner.report.get("summary", {}).get("result") == "ok":
        print("RESULT=OK")
        sys.exit(0)
    print("RESULT=FAILED")
    if args.assert_on_failure:
        sys.exit(1)



if __name__ == "__main__":
    main()
