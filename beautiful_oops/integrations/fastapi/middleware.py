# beautiful_oops/integrations/fastapi/middleware.py

from __future__ import annotations
from typing import Optional

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from beautiful_oops.core.adventure import Adventure
from beautiful_oops.core.oops import OopsError
from beautiful_oops.utils.trace_id_generator import TraceIdGenerator


class OopsAdventureMiddleware(BaseHTTPMiddleware):
    def __init__(
            self,
            app,
            *,
            name: str = "fastapi",
            header_trace_id: str = "X-Trace-Id",
            adventure_factory: Optional[callable] = None,
    ):
        super().__init__(app)
        self.name = name
        self.header_trace_id = header_trace_id
        self.adventure_factory = adventure_factory

    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get(self.header_trace_id) or TraceIdGenerator.new_trace_id()
        request.state.trace_id = trace_id

        adv = (
            self.adventure_factory(self.name, trace_id) if self.adventure_factory
            else Adventure(name=self.name, trace_id=trace_id)
        )

        async with Adventure.auto(adv):  # 异步上下文，避免 asyncio.run 嵌套
            try:
                response = await call_next(request)
                if isinstance(response, Response):
                    response.headers[self.header_trace_id] = trace_id
                return response

            except HTTPException as exc:
                # 显式捕获 FastAPI HTTPException，构造 OopsError 并透传状态码
                oe = OopsError.of(exc)
                oe.extra.setdefault("http_status", getattr(exc, "status_code", 500))
                return render_oops_response(oe, trace_id)

            except OopsError as oe:
                return render_oops_response(oe, trace_id)

            except Exception as e:
                return render_oops_response(OopsError.of(e), trace_id)


def render_oops_response(oops: OopsError, trace_id: str) -> JSONResponse:
    """同步：直接返回 JSONResponse，杜绝未 await 协程导致的 TypeError。"""
    status = int(oops.extra.get("http_status", 500))
    payload = {
        "trace_id": trace_id,
        "category": oops.category.value,
        "message": oops.safe_message,
    }
    resp = JSONResponse(status_code=status, content=payload)
    resp.headers["X-Trace-Id"] = trace_id
    return resp
