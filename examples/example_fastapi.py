from __future__ import annotations
import asyncio
import random

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request

# === Beautiful Oops: 核心 & 插件 & 集成中间件 ===
from beautiful_oops import (
    oops_moment,
    Adventure,
    OopsSolution,
    SimpleBackoffElf,
)
from beautiful_oops.plugins.storybook_plugin import StorybookPlugin
from beautiful_oops.plugins.storybook_console_sink_plugin import StorybookConsoleSinkPlugin
from beautiful_oops.integrations.fastapi.middleware import OopsAdventureMiddleware


# =====================================================
# 1) 业务函数（同步实现，装饰器返回 async 包装；路由里 await 调用）
# =====================================================

@oops_moment(chapter="Story", stage="decode_scroll")
def decode_scroll() -> str:
    return "ancient wisdom"


@oops_moment(
    chapter="Story", stage="reflect_illusion",
    elf=SimpleBackoffElf(rules={ValueError: OopsSolution.RETRY}, retries=2),
)
def reflect_illusion() -> str:
    if random.random() < 0.7:
        raise ValueError("mirror fog")
    return "clear vision"


@oops_moment(
    chapter="Story", stage="cross_bridge",
    elf=SimpleBackoffElf(rules={TypeError: OopsSolution.RETRY}, retries=3),
)
def cross_bridge() -> str:
    # 故意失败触发重试与失败收尾
    raise TypeError("bridge vanished")


# =====================================================
# 2) Adventure 工厂：为每个请求创建 Adventure + 插件
#    - StorybookPlugin 负责采集轨迹（moment/attempt）
#    - StorybookConsoleSinkPlugin 在 adv_end 时把整棵树打印到控制台
# =====================================================
def make_adventure(name: str, trace_id: str) -> Adventure:
    plugins = [
        StorybookPlugin(),
        StorybookConsoleSinkPlugin(),
    ]
    return Adventure(name=name, trace_id=trace_id, plugins=plugins, debug=False)


# =====================================================
# 3) FastAPI 应用 & 中间件：将 Adventure 挂在每个请求上
#    OopsAdventureMiddleware 支持 adventure_factory，交给工厂创建 adv
# =====================================================
def create_app() -> FastAPI:
    app = FastAPI(
        title="Beautiful Oops - FastAPI Trace Demo",
        description="Track entire call-chain via middleware + plugins, print tree at request end.",
        version="0.2.0",
    )

    # 通过 adventure_factory 把“每请求一个 Adventure + 插件”的逻辑注入中间件
    def adventure_factory(name: str, trace_id: str) -> Adventure:
        return make_adventure(name=name, trace_id=trace_id)

    # 传入自定义工厂（中间件内部会用 async with Adventure.auto(adv) 包好整个请求）
    app.add_middleware(
        OopsAdventureMiddleware,
        # 你自定义的名称会成为 StoryBook 标题
        name="my-fastapi-trace",
        # 透传 trace-id 的请求头名（可自定）
        header_trace_id="X-Trace-Id",
        # 关键：交给工厂构建 adv（挂好 Storybook & ConsoleSink 插件）
        adventure_factory=adventure_factory,  # ← 需要你在中间件里支持这个参数
    )

    register_routes(app)
    return app


def register_routes(app: FastAPI) -> None:
    @app.get("/ok")
    async def ok(request: Request):
        # 串起一条正常链路
        v = await decode_scroll()
        return {"ok": v, "trace_id": request.state.trace_id}

    @app.get("/flaky")
    async def flaky(request: Request):
        # 链路里有重试
        v = await reflect_illusion()
        return {"flaky": v, "trace_id": request.state.trace_id}

    @app.get("/fail")
    async def fail(request: Request):
        # 故意失败，观察轨迹收尾
        v = await cross_bridge()  # 将触发重试，最终失败
        return {"fail": v, "trace_id": request.state.trace_id}

    @app.get("/boom")
    async def boom():
        # 非业务异常，走 middleware 的 Oops 安全化输出
        raise HTTPException(status_code=503, detail="temp outage")


# =====================================================
# 4) 启动 server 并自动打几次请求，控制台查看“树”
# =====================================================
async def fire_demo_requests(port: int = 8000) -> None:
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
        print("\n🚀 Sending demo requests (see console for tree output by ConsoleSink):")
        for path in ["/ok", "/flaky", "/fail", "/boom"]:
            r = await client.get(path)
            print(f">>> GET {path} | {r.status_code} | X-Trace-Id={r.headers.get('X-Trace-Id')}")
            print("    Body:", r.text)


async def main_async():
    config = uvicorn.Config(
        app=create_app(),
        host="127.0.0.1",
        port=8000,
        log_level="warning",
        reload=False,
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    await asyncio.sleep(1.0)  # 等待服务起来
    try:
        await fire_demo_requests()
    finally:
        server.should_exit = True
        await task
    print("\n✅ Demo done. Check the console above for per-request trees from ConsoleSink.")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
