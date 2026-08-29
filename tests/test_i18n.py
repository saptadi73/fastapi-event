import unittest
from types import SimpleNamespace

from app.core.i18n import normalize_locale, request_locale, translate_message
from app.modules.email_notifications.service import DEFAULT_TEMPLATES_BY_LOCALE, TRIGGER_VARIABLES
from app.modules.users.schemas import UserCreate, UserUpdate
from app.support.responses import fail_response, success_response
from starlette.requests import Request
from starlette.responses import Response
from app.middleware.locale import LocaleMiddleware
from app.core.i18n import translate_error_message
from app.main import app
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
import json
from unittest.mock import patch
from unittest.mock import AsyncMock
from app.modules.payments import routes as payment_routes


class _Request:
    def __init__(self, query=None, headers=None):
        self.query_params = query or {}
        self.headers = headers or {}
        self.state = SimpleNamespace(request_id="req-i18n")


class I18nTest(unittest.TestCase):
    def test_locale_normalization(self):
        self.assertEqual("zh-CN", normalize_locale("zh-Hans-CN"))
        self.assertEqual("zh-CN", normalize_locale("zh_cn"))
        self.assertEqual("en", normalize_locale("en-US"))
        self.assertEqual("en", normalize_locale("id-ID"))

    def test_query_locale_wins_over_accept_language(self):
        request = _Request({"locale": "en"}, {"accept-language": "zh-CN,zh;q=0.9"})
        self.assertEqual("en", request_locale(request))

    def test_response_message_can_be_simplified_chinese(self):
        request = _Request(headers={"accept-language": "zh-CN"})
        success = success_response("Login berhasil", request=request)
        failure = fail_response(
            "Validation failed",
            [{"field": "email", "code": "INVALID", "message": "Email atau password salah"}],
            request,
        )
        self.assertEqual("登录成功", success["message"])
        self.assertEqual("验证失败", failure["message"])
        self.assertEqual("邮箱或密码错误", failure["errors"][0]["message"])
        self.assertEqual("INVALID", failure["errors"][0]["code"])

    def test_error_code_is_stable_translation_key(self):
        self.assertEqual("未找到订单", translate_error_message("ORDER_NOT_FOUND", "Any source message", "zh-CN"))
        self.assertEqual("Any source message", translate_error_message("ORDER_NOT_FOUND", "Any source message", "en"))
        self.assertEqual("请求无法处理（NEW_DOMAIN_ERROR）", translate_error_message("NEW_DOMAIN_ERROR", "Pesan baru", "zh-CN"))

    def test_unknown_success_message_never_leaks_indonesian_to_chinese_response(self):
        response = success_response("Pesan module baru", request=_Request(headers={"accept-language": "zh-CN"}))
        self.assertEqual("操作成功", response["message"])

    def test_common_pydantic_message_is_localized(self):
        self.assertEqual("字符串至少需要 8 个字符", translate_message("String should have at least 8 characters", "zh-CN"))

    def test_user_locale_contract(self):
        created = UserCreate(email="hello@example.com", password="password1", country="China", phone="12345678", preferred_locale="zh-CN")
        self.assertEqual("zh-CN", created.preferred_locale)
        self.assertEqual("zh-CN", UserUpdate(preferred_locale="zh-CN").preferred_locale)

    def test_every_trigger_has_bilingual_default(self):
        self.assertEqual(set(TRIGGER_VARIABLES), set(DEFAULT_TEMPLATES_BY_LOCALE["en"]))
        self.assertEqual(set(TRIGGER_VARIABLES), set(DEFAULT_TEMPLATES_BY_LOCALE["zh-CN"]))
        self.assertEqual("欢迎参加 {{ event_name }}", DEFAULT_TEMPLATES_BY_LOCALE["zh-CN"]["account_registered"][0])

    def test_openapi_documents_global_locale_contract(self):
        schema = app.openapi()
        parameter = schema["components"]["parameters"]["LocaleQuery"]
        self.assertEqual(["en", "zh-CN"], parameter["schema"]["enum"])
        health_parameters = schema["paths"]["/api/v1/health"]["get"]["parameters"]
        self.assertIn({"$ref": "#/components/parameters/LocaleQuery"}, health_parameters)



class LocaleMiddlewareTest(unittest.IsolatedAsyncioTestCase):
    async def test_http_response_declares_selected_language(self):
        request = Request({
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": [(b"accept-language", b"zh-CN")],
        })

        async def call_next(_request):
            return Response("ok")

        middleware = LocaleMiddleware(lambda scope, receive, send: None)
        with patch("app.middleware.locale.logger.info") as log_info:
            response = await middleware.dispatch(request, call_next)
        self.assertEqual("zh-CN", response.headers["content-language"])
        self.assertIn("Accept-Language", response.headers["vary"])
        fields = log_info.call_args.kwargs["extra"]
        self.assertEqual("zh-CN", fields["locale"])
        self.assertEqual("GET", fields["method"])
        self.assertEqual(200, fields["status_code"])
        self.assertNotIn("headers", fields)

    async def test_http_exception_uses_localized_stable_error_contract(self):
        request = Request({
            "type": "http", "method": "GET", "path": "/", "query_string": b"",
            "headers": [(b"accept-language", b"zh-CN")],
        })
        response = await app.exception_handlers[HTTPException](request, HTTPException(403, "Organizer role required"))
        payload = json.loads(response.body)
        self.assertEqual(403, response.status_code)
        self.assertEqual("FORBIDDEN", payload["errors"][0]["code"])
        self.assertEqual("没有执行此操作的权限", payload["message"])

        english_request = Request({
            "type": "http", "method": "GET", "path": "/", "query_string": b"",
            "headers": [(b"accept-language", b"en")],
        })
        english_response = await app.exception_handlers[HTTPException](english_request, HTTPException(403, "Organizer role required"))
        english_payload = json.loads(english_response.body)
        self.assertEqual(response.status_code, english_response.status_code)
        self.assertEqual(payload["errors"][0]["code"], english_payload["errors"][0]["code"])

    async def test_request_validation_message_is_localized(self):
        request = Request({
            "type": "http", "method": "POST", "path": "/", "query_string": b"",
            "headers": [(b"accept-language", b"zh-CN")],
        })
        exc = RequestValidationError([{
            "type": "missing", "loc": ("body", "name"), "msg": "Field required", "input": {},
        }])
        response = await app.exception_handlers[RequestValidationError](request, exc)
        payload = json.loads(response.body)
        self.assertEqual(422, response.status_code)
        self.assertEqual("missing", payload["errors"][0]["code"])
        self.assertEqual("此字段为必填项", payload["errors"][0]["message"])

    async def test_payment_webhook_machine_result_is_locale_invariant(self):
        async def request_for(locale):
            consumed = False

            async def receive():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {"type": "http.request", "body": b'{"transaction":"paid"}', "more_body": False}
                return {"type": "http.disconnect"}

            return Request({
                "type": "http", "method": "POST", "path": "/webhooks/doku", "query_string": b"",
                "headers": [(b"accept-language", locale.encode())],
            }, receive)

        with patch.object(payment_routes.PaymentService, "handle_doku_notification", AsyncMock(return_value="success")):
            english = await payment_routes.doku_notification(await request_for("en"), db=object())
            chinese = await payment_routes.doku_notification(await request_for("zh-CN"), db=object())

        self.assertEqual(english["data"], chinese["data"])
        self.assertEqual({"result": "success"}, chinese["data"])
        self.assertEqual("Notifikasi DOKU diproses", english["message"])
        self.assertEqual("DOKU 通知已处理", chinese["message"])


if __name__ == "__main__":
    unittest.main()
