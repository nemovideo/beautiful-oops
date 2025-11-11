from __future__ import annotations
from enum import Enum
import asyncio
import errno
import socket
import ssl
import http.client
from typing import Optional, Tuple, Any


class OopsSolution(Enum):
    RETRY = "retry"
    ABORT = "abort"
    IGNORE = "ignore"
    FALLBACK = "fallback"


class OopsCategory(Enum):
    IO = "io"
    NETWORK = "network"
    TIMEOUT = "timeout"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    BAD_REQUEST = "bad_request"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


class OopsError(RuntimeError):
    def __init__(
        self,
        cause: Exception,
        message: Optional[str] = None,
        safe_message: Optional[str] = None,
        category: Optional[OopsCategory] = None,
        advise: Optional[OopsSolution] = None,
        extra: Optional[dict[str, Any]] = None,
    ):
        self.cause = cause
        self.message = message or str(cause) or cause.__class__.__name__

        auto_cat, http_status = _classify_exception(cause, self.message)
        self.category = category or auto_cat

        self.safe_message = safe_message or _safe_message_by_category(self.category)
        self.advise = advise or _default_advise(self.category)

        self.extra = extra or {}
        if http_status is not None:
            self.extra.setdefault("http_status", http_status)

        super().__init__(self.message)

    @classmethod
    def of(cls, e: Exception) -> "OopsError":
        return cls(cause=e)


def _safe_message_by_category(cat: OopsCategory) -> str:
    messages = {
        OopsCategory.IO: "File or disk access failed.",
        OopsCategory.NETWORK: "Network connection failed.",
        OopsCategory.TIMEOUT: "Operation timed out.",
        OopsCategory.AUTH: "Authentication failed. Please check credentials.",
        OopsCategory.RATE_LIMIT: "Too many requests. Please try again later.",
        OopsCategory.VALIDATION: "Input data validation failed.",
        OopsCategory.BAD_REQUEST: "Invalid request format or missing required parameters.",
        OopsCategory.UNKNOWN: "An unexpected error occurred.",
    }
    return messages.get(cat, "An unexpected error occurred.")


def _default_advise(cat: OopsCategory):
    if cat in (OopsCategory.TIMEOUT, OopsCategory.NETWORK, OopsCategory.RATE_LIMIT):
        return OopsSolution.RETRY
    if cat == OopsCategory.AUTH:
        return OopsSolution.ABORT
    if cat == OopsCategory.IO:
        return OopsSolution.FALLBACK
    return OopsSolution.ABORT


def _classify_exception(e: Exception, message: str) -> Tuple[OopsCategory, Optional[int]]:
    if isinstance(e, (asyncio.TimeoutError, TimeoutError, socket.timeout)):
        return OopsCategory.TIMEOUT, None

    if isinstance(
        e,
        (
            ConnectionError,
            ConnectionAbortedError,
            ConnectionRefusedError,
            ConnectionResetError,
            BrokenPipeError,
            ssl.SSLError,
            http.client.RemoteDisconnected,
            http.client.CannotSendRequest,
            http.client.CannotSendHeader,
        ),
    ):
        return OopsCategory.NETWORK, None

    if isinstance(e, (ValueError, TypeError, AssertionError)):
        return OopsCategory.VALIDATION, None

    if isinstance(e, OSError) and getattr(e, "errno", None) in {
        errno.EIO, errno.EROFS, errno.ENOSPC, errno.ENOENT, errno.EACCES
    }:
        return OopsCategory.IO, None

    status = _guess_http_status(e)
    if status is not None:
        if status == 429:
            return OopsCategory.RATE_LIMIT, status
        if status in (401, 403):
            return OopsCategory.AUTH, status
        if 500 <= status <= 599:
            return OopsCategory.NETWORK, status
        if status in (408,):
            return OopsCategory.TIMEOUT, status

    if "service unavailable" in message or "socket closed" in message:
        return OopsCategory.NETWORK, 503

    if "validation" in message or "invalid" in message or "schema" in message:
        return OopsCategory.VALIDATION, 400

    if "badrequest" in message or "invalid_request_error" in message:
        return OopsCategory.BAD_REQUEST, 400

    return OopsCategory.UNKNOWN, status


def _guess_http_status(e: Exception) -> Optional[int]:
    for attr in ("status_code", "status"):
        try:
            val = getattr(e, "response", None)
            if val is not None:
                code = getattr(val, "status_code", None) or getattr(val, "status", None)
                if isinstance(code, int):
                    return code
            code = getattr(e, attr, None)
            if isinstance(code, int):
                return code
        except Exception:
            pass
    return None
