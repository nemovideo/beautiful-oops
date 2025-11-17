from __future__ import annotations
from typing import Callable, Optional, Protocol, Any, Dict

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response, PlainTextResponse

from beautiful_oops.core.adventure import Adventure
from beautiful_oops.plugins.storybook_plugin import StorybookPlugin
from beautiful_oops.plugins.storybook_console_sink_plugin import StorybookConsoleSinkPlugin
from beautiful_oops.core.oops import OopsError
from beautiful_oops.utils.trace_id_generator import TraceIdGenerator


# =========================
#   渲染函数协议 & 工厂
# =========================

class RenderFunc(Protocol):
    def __call__(self, oops: OopsError, trace_id: str, request: Request) -> Response: ...


def default_payload_builder(oops: OopsError, trace_id: str, request: Request) -> Dict[str, Any]:
    """默认 JSON payload，可被复用或覆盖。"""
    return {
        "trace_id": trace_id,
        "category": oops.category.value,
        "message": oops.safe_message,
    }


def make_json_render(
        *,
        header_trace_id: str = "X-Trace-Id",
        status_extra_key: str = "http_status",
        payload_builder: Callable[[OopsError, str, Request], Dict[str, Any]] = default_payload_builder,
) -> RenderFunc:
    """
    生成一个返回 JSONResponse 的渲染函数：

    - 状态码从 oops.extra[status_extra_key] 读取，默认 500。
    - body 由 payload_builder(oops, trace_id, request) 构造。
    """

    def render(oops: OopsError, trace_id: str, request: Request) -> JSONResponse:
        status = int(oops.extra.get(status_extra_key, 500))
        payload = payload_builder(oops, trace_id, request)
        resp = JSONResponse(status_code=status, content=payload)
        resp.headers[header_trace_id] = trace_id
        return resp

    return render


def make_plaintext_render(
        *,
        header_trace_id: str = "X-Trace-Id",
        status_extra_key: str = "http_status",
) -> RenderFunc:
    """简单文本版渲染，方便 CLI / debug 环境。"""

    def render(oops: OopsError, trace_id: str, request: Request) -> PlainTextResponse:
        status = int(oops.extra.get(status_extra_key, 500))
        text = f"[trace_id={trace_id}] {oops.category.value}: {oops.safe_message}"
        resp = PlainTextResponse(status_code=status, content=text)
        resp.headers[header_trace_id] = trace_id
        return resp

    return render


# =========================
#   默认 Adventure 工厂
# =========================

AdventureFactory = Callable[[str, str, Request], Adventure]


def default_adventure_factory(
        name: str,
        trace_id: str,
        request: Request,
) -> Adventure:
    """
    默认的 Adventure 构造策略：
    - name：你传进来的 name（一般包含 path + trace_id）
    - trace_id：沿用 middleware 生成 / 传入的 trace_id
    - plugins：StorybookPlugin + StorybookConsoleSinkPlugin
    """
    return Adventure(
        name,
        trace_id=trace_id,
        plugins=[StorybookPlugin(), StorybookConsoleSinkPlugin()],
        debug=True,
    )


# =========================
#   OopsMiddleware 主体
# =========================

class OopsMiddleware(BaseHTTPMiddleware):
    """
    通用的 Beautiful Oops FastAPI/Starlette 中间件：

    功能：
    - 每个请求生成 / 透传 trace_id（默认 header: X-Trace-Id）
    - 为每个请求构建一个 Adventure 并放进上下文（Adventure.auto）
    - 捕获 HTTPException / OopsError / 其他异常并用渲染函数输出 Response

    可配置项：
    - name: 用于构造 adventure 名字的前缀
    - header_trace_id: 从哪个 header 读写 trace_id
    - adventure_factory: 定制 Adventure 的构造逻辑
    - render: 决定错误时如何输出 Response（JSON / 文本 / HTML）
    """

    def __init__(
            self,
            app,
            *,
            name: str = "request path",
            header_trace_id: str = "X-Trace-Id",
            adventure_factory: Optional[AdventureFactory] = None,
            render: Optional[RenderFunc] = None,
    ):
        super().__init__(app)
        self.name = name
        self.header_trace_id = header_trace_id
        self._adventure_factory = adventure_factory or default_adventure_factory
        self._render = render or make_json_render(header_trace_id=header_trace_id)

    async def dispatch(self, request: Request, call_next):
        # 1. 生成或复用 trace_id
        trace_id = request.headers.get(self.header_trace_id) or TraceIdGenerator.new_trace_id()
        request.state.trace_id = trace_id

        # 2. 生成 Adventure（注意：不要在 dispatch 里覆写 self._adventure_factory）
        adv_name = f"{self.name} [{request.method} {request.url.path}] [{trace_id}]"
        adv = self._adventure_factory(adv_name, trace_id, request)

        # 3. 进入 Adventure 上下文，完成一次请求的“故事”
        async with Adventure.auto(adv):
            try:
                response = await call_next(request)
                # SSE / StreamingResponse / 普通 JSONResponse 都是 Response 的子类
                if isinstance(response, Response):
                    response.headers[self.header_trace_id] = trace_id
                return response

            except HTTPException as exc:
                # 显式捕获 FastAPI HTTPException
                oe = OopsError.of(exc)
                oe.extra.setdefault("http_status", getattr(exc, "status_code", 500))
                return self._render(oe, trace_id, request)

            except OopsError as oe:
                # 业务代码里已经主动抛出了 OopsError
                return self._render(oe, trace_id, request)

            except BaseException as e:
                # 兜底：其他异常全部转为 OopsError
                return self._render(OopsError.of(e), trace_id, request)
