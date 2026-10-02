"""Agent 名片。

对应 Java 版的 A2AConfiguration#agentCard。
客户端第一件事就是来拉这个，拿到之后才知道把请求发去哪、这个 Agent 会干什么。

注意：a2a-sdk 1.x 实现的是 A2A 1.0 规范，名片的调用地址写在
supported_interfaces 列表里（老版的 url 字段已经没有了）。
"""

from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill

from app import settings


def build_agent_card() -> AgentCard:
    return AgentCard(
        name=settings.AGENT_NAME,
        description=settings.AGENT_DESCRIPTION,
        version=settings.AGENT_VERSION,
        # 客户端从「支持的接口」列表里挑一个来调我们
        supported_interfaces=[
            AgentInterface(
                url=settings.AGENT_URL,
                protocol_binding="JSONRPC",
            )
        ],
        # 声明「我会哪几手」。声明了就必须实现，否则是给客户端挖坑：
        #   streaming          → 必须实现 message/stream
        #   push_notifications → 必须实现 4 个 webhook 配置方法（这里先关掉）
        capabilities=AgentCapabilities(
            streaming=True,
            push_notifications=False,
            #不主动推送消息
        ),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id="sql",
                name="sql generator",
                description="Generate a SQL query",
                tags=["sql", "query"],
            )
        ],
    )
