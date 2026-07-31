from datetime import datetime, timezone
from typing import Any

from fastapi import Request


def _request_id(request: Request | None) -> str:
    if request is None:
        return ""
    return getattr(request.state, "request_id", "") or ""


def success_response(message: str, data: Any | None = None, meta: Any | None = None, request: Request | None = None):
    return {
        "success": True,
        "message": message,
        "data": data,
        "meta": meta,
        "request_id": _request_id(request),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def fail_response(message: str, errors: list[dict] | None = None, request: Request | None = None):
    return {
        "success": False,
        "message": message,
        "errors": errors or [],
        "request_id": _request_id(request),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
