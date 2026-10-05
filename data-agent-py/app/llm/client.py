"""聊天模型客户端。

对应 Java 版 ChatClientConfig 里那个 deepseekClient。

【和 embeddings.py 的区别】
  embeddings.py 调的是"向量化"接口（文本 → 一串数字）。
  这个文件调的是"对话"接口（文本 → 文本）。两个是不同的模型、不同的活。
"""

import logging

from openai import OpenAI

from app import settings

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.DASHSCOPE_API_KEY:
            raise RuntimeError(
                "没有配置 DASHSCOPE_API_KEY。请在 data-agent-py/.env 里填上你的 key。"
            )
        _client = OpenAI(
            api_key=settings.DASHSCOPE_API_KEY,
            base_url=settings.DASHSCOPE_BASE_URL,
        )
    return _client


def chat(prompt: str | None = None, system: str | None = None) -> str:
    """发一次对话请求，返回模型输出的纯文本。

    三种用法：
        chat("问题")                     → 只发一条 user 消息
        chat("问题", system="你是助手")   → system + user 两条
        chat(system=长提示词)            → 只发一条 system 消息
                                          （SQL 生成节点就是这种用法，
                                           Java 里写的是 .system(sqlPrompt)）

    【enable_thinking=False 是必须的】
      Java 版每个 LLM 调用都带这个参数。不关掉"思考模式"的话，
      DashScope 会把思维链一起塞进返回内容里，导致后面按 JSON 解析时
      大面积失败——而且报错信息看不出来是这个原因。
    """
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    if prompt:
        messages.append({"role": "user", "content": prompt})
    if not messages:
        raise ValueError("chat() 至少要有一个 prompt 或 system")

    response = _get_client().chat.completions.create(
        model=settings.CHAT_MODEL,
        messages=messages,
        extra_body={"enable_thinking": False},
    )
    content = response.choices[0].message.content or ""
    logger.debug("LLM 返回 %d 字符", len(content))
    return content
