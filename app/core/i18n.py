from __future__ import annotations

from fastapi import Request
import re

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = ("en", "zh-CN")


def normalize_locale(value: str | None, default: str = DEFAULT_LOCALE) -> str:
    if not value:
        return default
    candidate = value.strip().replace("_", "-").lower()
    if candidate == "en" or candidate.startswith("en-"):
        return "en"
    if candidate in {"zh", "zh-cn", "zh-hans"} or candidate.startswith("zh-hans-"):
        return "zh-CN"
    return default


def request_locale(request: Request | None, default: str = DEFAULT_LOCALE) -> str:
    if request is None:
        return default
    query_locale = getattr(request, "query_params", {}).get("locale")
    if query_locale:
        return normalize_locale(query_locale, default)
    accept_language = getattr(request, "headers", {}).get("accept-language", "")
    for part in accept_language.split(","):
        language = part.split(";", 1)[0].strip()
        normalized = normalize_locale(language, "")
        if normalized:
            return normalized
    return default


_ZH_MESSAGES = {
    "Validation failed": "验证失败",
    "Database constraint violation": "数据库约束冲突",
    "Data profil berhasil diambil": "个人资料获取成功",
    "Profil berhasil diperbarui": "个人资料更新成功",
    "Registrasi akun berhasil": "账户注册成功",
    "Login berhasil": "登录成功",
    "Logout berhasil": "退出登录成功",
    "Token di-refresh": "令牌刷新成功",
    "Instruksi reset password telah dikirim": "密码重置说明已发送",
    "Password berhasil diubah": "密码修改成功",
    "Email berhasil diverifikasi": "邮箱验证成功",
    "User tidak ditemukan": "未找到用户",
    "Email sudah terdaftar": "该邮箱已注册",
    "Email atau password salah": "邮箱或密码错误",
    "Token tidak valid": "令牌无效",
    "Refresh token tidak valid": "刷新令牌无效",
    "Token bukan refresh token": "该令牌不是刷新令牌",
    "Password saat ini tidak sesuai": "当前密码不正确",
    "Konfirmasi password tidak cocok": "两次输入的密码不一致",
    "Password baru harus berbeda dari password lama": "新密码必须与旧密码不同",
    "Missing bearer token": "缺少身份验证令牌",
    "Invalid bearer token": "身份验证令牌无效",
    "Bearer token expired": "身份验证令牌已过期",
    "Invalid token type": "令牌类型无效",
    "Invalid user": "用户无效",
    "Organizer role required": "需要主办方权限",
    "Translation target was not found": "未找到翻译目标",
    "Content translation was not found": "未找到内容翻译",
    "Supported locales are en and zh-CN": "支持的语言为 en 和 zh-CN",
}

_ZH_ERROR_CODES = {
    "UNAUTHORIZED": "未授权访问",
    "FORBIDDEN": "没有执行此操作的权限",
    "NOT_FOUND": "未找到资源",
    "CONFLICT": "资源状态冲突",
    "VALIDATION_ERROR": "请求验证失败",
    "USER_NOT_FOUND": "未找到用户",
    "USER_EXISTS": "该邮箱已注册",
    "INVALID_CREDENTIAL": "邮箱或密码错误",
    "INVALID_TOKEN": "令牌无效",
    "PASSWORD_MISMATCH": "两次输入的密码不一致",
    "WEAK_PASSWORD": "新密码必须与旧密码不同",
    "EVENT_NOT_FOUND": "未找到活动",
    "PRODUCT_NOT_FOUND": "未找到产品或产品不可用",
    "EMPTY_CART": "购物车为空",
    "CART_ITEM_NOT_FOUND": "购物车中未找到该项目",
    "MIXED_CURRENCY": "同一订单中的产品必须使用相同货币",
    "INVALID_DELEGATE_SELECTION": "代表套餐或价格选择无效",
    "MAIN_PACKAGE_REQUIRED": "必须且只能选择一个主套餐",
    "DUPLICATE_PACKAGE_SELECTION": "每个套餐只能选择一个价格选项",
    "PAYMENT_NOT_FOUND": "未找到付款记录",
    "ORDER_NOT_FOUND": "未找到订单",
    "INVALID_PAYMENT_STATUS": "付款状态无效",
    "INVALID_ORDER_STATUS": "订单状态无效",
    "UPLOAD_STORAGE_ERROR": "文件存储失败",
    "INVALID_IMAGE_TYPE": "不支持的图片类型",
    "IMAGE_TOO_LARGE": "图片文件过大",
    "INVALID_EMAIL_TRIGGER": "邮件通知触发器无效",
    "EMAIL_TEMPLATE_NOT_FOUND": "未找到邮件模板",
    "INVALID_TEMPLATE_VARIABLE": "邮件模板包含无效变量",
    "INVALID_TRANSLATION_ENTITY": "不支持该翻译实体类型",
    "INVALID_TRANSLATION_FIELD": "包含不可翻译的字段",
    "INVALID_TRANSLATION_VALUE": "翻译内容值无效",
    "TRANSLATION_ENTITY_NOT_FOUND": "未找到翻译目标",
    "CONTENT_TRANSLATION_NOT_FOUND": "未找到内容翻译",
    "UNSUPPORTED_LOCALE": "支持的语言为 en 和 zh-CN",
    "MEETING_SCHEDULE_CONFLICT": "会议时间或场地冲突",
    "INVALID_MEETING_TRANSITION": "不允许此会议状态变更",
    "MESSAGE_NOT_FOUND": "未找到消息",
    "EMPTY_MESSAGE": "消息内容不能为空",
    "TICKET_NOT_FOUND": "未找到门票",
    "CHECKIN_DUPLICATE": "该门票已签到",
}


def translate_message(message: str, locale: str) -> str:
    if locale == "zh-CN":
        translated = _ZH_MESSAGES.get(message)
        if translated:
            return translated
        validation_patterns = (
            (r"^Field required$", "此字段为必填项"),
            (r"^Input should be a valid UUID.*$", "请输入有效的 UUID"),
            (r"^Input should be a valid (integer|number).*$", "请输入有效数字"),
            (r"^Input should be a valid string.*$", "请输入有效字符串"),
            (r"^String should have at least (\d+) characters$", r"字符串至少需要 \1 个字符"),
            (r"^String should have at most (\d+) characters$", r"字符串最多允许 \1 个字符"),
            (r"^Input should be greater than or equal to (.+)$", r"输入值必须大于或等于 \1"),
        )
        for pattern, replacement in validation_patterns:
            if re.match(pattern, message):
                return re.sub(pattern, replacement, message)
    return message


def translate_error_message(code: str | None, message: str, locale: str) -> str:
    if locale == "zh-CN":
        if code in _ZH_ERROR_CODES:
            return _ZH_ERROR_CODES[code]
        translated = translate_message(message, locale)
        if translated != message:
            return translated
        if code and re.fullmatch(r"[A-Z][A-Z0-9_]+", code):
            return f"请求无法处理（{code}）"
        if code:
            return "输入内容无效"
    return message
