"""调 DashScope 把文本变成向量。

对应 Java 版的 Spring AI EmbeddingModel。

注意两个约束（都来自 DashScope）：
  1. text-embedding-v4 一次请求最多 10 条文本
  2. 维度固定 1024（和 pgvector 表里的 vector(1024) 必须一致）
"""

from openai import OpenAI

from app import settings

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


def embed_texts(texts: list[str]) -> list[list[float]]:
    """把一批文本转成向量，返回顺序与输入一致。"""
    response = _get_client().embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=texts,
        dimensions=settings.EMBEDDING_DIMENSIONS,
    )
    # API 不保证返回顺序，按 index 排序后再取
    items = sorted(response.data, key=lambda d: d.index)
    return [item.embedding for item in items]


def embed_one(text: str) -> list[float]:
    """单条文本转向量（调试用）。"""
    return embed_texts([text])[0]
