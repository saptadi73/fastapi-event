import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.modules.payments.doku_snap import DokuSnapClient, symmetric_signature


class DokuVaChannelTests(unittest.IsolatedAsyncioTestCase):
    async def test_channel_is_normalized_before_payload_is_signed_and_sent(self):
        expected_channels = {
            "mandiri": "VIRTUAL_ACCOUNT_BANK_MANDIRI",
            "BCA": "VIRTUAL_ACCOUNT_BCA",
            "BNI": "VIRTUAL_ACCOUNT_BNI",
            "BRI": "VIRTUAL_ACCOUNT_BRI",
            "BSI": "VIRTUAL_ACCOUNT_BSI",
        }
        for bank, expected in expected_channels.items():
            with self.subTest(bank=bank):
                client = DokuSnapClient()
                client.settings = SimpleNamespace(
                    DOKU_SNAP_VA_CREATE_PATH="/virtual-accounts/bi-snap-va/v1.1/transfer-va/create-va",
                    DOKU_SNAP_PARTNER_ID="test-partner",
                    DOKU_SNAP_CHANNEL_ID="H2H",
                    DOKU_SNAP_CLIENT_SECRET="test-secret",
                )
                payload = {
                    "totalAmount": {"value": "9900000.00", "currency": "IDR"},
                    "additionalInfo": {
                        "channel": f"VIRTUAL_ACCOUNT_{bank.upper()}",
                        "virtualAccountConfig": {"reusableStatus": False},
                    },
                }
                response = {"responseCode": "2002700", "virtualAccountData": {"virtualAccountNo": "123456789"}}
                with patch.object(client, "_validate"), patch.object(client, "va_channels", return_value={bank.upper(): {"partner_service_id": "   70002", "customer_no": "4"}}), patch.object(client, "access_token", AsyncMock(return_value="test-token")), patch.object(client, "_send", AsyncMock(return_value=(response, {}))) as send:
                    result, external_id = await client.create_va(bank, payload)
                path, headers, sent = send.call_args.args
                self.assertEqual(sent["additionalInfo"]["channel"], expected)
                self.assertEqual(sent["additionalInfo"]["virtualAccountConfig"], {"reusableStatus": False})
                self.assertEqual(sent["totalAmount"]["value"], "9900000.00")
                self.assertEqual(sent["partnerServiceId"], "   70002")
                self.assertEqual(sent["customerNo"], "4")
                self.assertEqual(headers["X-SIGNATURE"], symmetric_signature("POST", path, "test-token", sent, headers["X-TIMESTAMP"], "test-secret"))
                self.assertEqual(result, response)
                self.assertEqual(external_id, headers["X-EXTERNAL-ID"])

    async def test_mandiri_channel_is_added_when_caller_omits_additional_info(self):
        client = DokuSnapClient()
        payload = {"totalAmount": {"value": "10000.00", "currency": "IDR"}}
        with patch.object(client, "_validate"), patch.object(client, "va_channels", return_value={"MANDIRI": {"partner_service_id": "   70002"}}), patch.object(client, "access_token", AsyncMock(return_value="test-token")), patch.object(client, "_send", AsyncMock(return_value=({"responseCode": "2002700"}, {}))) as send:
            await client.create_va("MANDIRI", payload)
        self.assertEqual(send.call_args.args[2]["additionalInfo"], {"channel": "VIRTUAL_ACCOUNT_BANK_MANDIRI"})
