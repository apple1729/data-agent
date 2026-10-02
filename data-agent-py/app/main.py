"""启动入口。

对应 Java 版的 A2AController + A2AConfiguration#jsonRpcHandler：
把「名片 + 执行器 + 任务存储」组装成一个 FastAPI 应用。

两个路由都由 SDK 提供，不用手写：
  create_agent_card_routes → GET /.well-known/agent-card.json
  create_jsonrpc_routes    → POST /a2a/jsonrpc（含 SSE 推流）
"""

import logging

import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from fastapi import FastAPI

from app import settings
from app.a2a.agent_card import build_agent_card
from app.a2a.executor import GraphAgentExecutor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s | %(message)s",
)


def build_app():
    agent_card = build_agent_card()

    request_handler = DefaultRequestHandler(
        agent_executor=GraphAgentExecutor(),
        # 内存版任务存储：重启即丢。阶段 4 要换成持久化版本，
        # 否则人工审核跑到一半重启，现场就没了。
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    app = FastAPI(title="data-agent-py")
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(agent_card),
        jsonrpc_routes=create_jsonrpc_routes(
            request_handler,
            rpc_url="/a2a/jsonrpc",
            # 前端和 Java 版都是 A2A 0.3.x，这里打开 0.3 兼容开关，
            # 保证它们发过来的老格式请求还能被正确解析。
            enable_v0_3_compat=True,
        ),
    )
    return app


app = build_app()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT)
