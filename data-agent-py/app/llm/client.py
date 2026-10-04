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


def chat(prompt: str, system: str | None = None) -> str:
    """发一次对话请求，返回模型输出的纯文本。

    【enable_thinking=False 是必须的】
      Java 版每个 LLM 调用都带这个参数。不关掉"思考模式"的话，
      DashScope 会把思维链一起塞进返回内容里，导致后面按 JSON 解析时
      大面积失败——而且报错信息看不出来是这个原因。
    """
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = _get_client().chat.completions.create(
        model=settings.CHAT_MODEL,
        messages=messages,
        extra_body={"enable_thinking": False},
    )
    content = response.choices[0].message.content or ""
    logger.debug("LLM 返回 %d 字符", len(content))
    return content
