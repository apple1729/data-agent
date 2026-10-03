"""向量库：建表、写入、检索。

对应 Java 版的 Spring AI VectorStore（底层就是 PostgreSQL + pgvector）。

Java 版这张表是 Spring AI 启动时自动建的，Python 版没有那套机制，
所以这里自己建一张，结构从简：id / content / metadata / embedding。
"""

import json
import uuid

from sqlalchemy import text

from app import settings
from app.db.session import engine
from app.retrieval.document_mapper import VectorDocument

# 建表 + 索引。IF NOT EXISTS 保证可以反复执行。
_DDL = f"""
CREATE TABLE IF NOT EXISTS vector_store (
    id        UUID PRIMARY KEY,
    content   TEXT NOT NULL,
    metadata  JSONB,
    embedding VECTOR({settings.EMBEDDING_DIMENSIONS})
);
CREATE INDEX IF NOT EXISTS idx_vector_store_metadata
    ON vector_store USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_vector_store_embedding
    ON vector_store USING hnsw (embedding vector_cosine_ops);
"""


def init_schema() -> None:
    """建向量表。重复执行安全。"""
    with engine.begin() as conn:
        # DDL 里有多条语句，psycopg 需要分开执行
        for statement in _DDL.split(";"):
            if statement.strip():
                conn.execute(text(statement))


def add_documents(docs: list[VectorDocument], embeddings: list[list[float]]) -> None:
    """批量写入。docs 和 embeddings 必须一一对应。"""
    if not docs:
        return
    if len(docs) != len(embeddings):
        raise ValueError(f"文档数({len(docs)})和向量数({len(embeddings)})不一致")

    rows = [
        {
            "id": str(uuid.uuid4()),
            "content": doc.text,
            "metadata": json.dumps(doc.metadata, ensure_ascii=False),
            "embedding": _to_vector_literal(emb),
        }
        for doc, emb in zip(docs, embeddings)
    ]
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO vector_store (id, content, metadata, embedding) "
                "VALUES (:id, :content, CAST(:metadata AS JSONB), CAST(:embedding AS VECTOR))"
            ),
            rows,
        )


def search(
    query_embedding: list[float],
    database_id: str,
    vector_type: str,
    top_k: int = 4,
) -> list[dict]:
    """带过滤的相似度检索。

    WHERE 里同时按 vectorType 和 databaseId 过滤——这是 Java 版的设计，
    避免"跨库串味"和"表和术语混在一起"。

    返回：按相似度从高到低排好的 [{id, content, metadata, score, ...}]
    score 是余弦相似度（1 - 余弦距离），越接近 1 越相似。
    """
    sql = text(
        """
        SELECT id,
               content,
               metadata,
               1 - (embedding <=> CAST(:vec AS VECTOR)) AS score
        FROM vector_store
        WHERE metadata->>'vectorType' = :vtype
          AND metadata->>'databaseId' = :dbid
        ORDER BY embedding <=> CAST(:vec AS VECTOR)
        LIMIT :topk
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(
            sql,
            {
                "vec": _to_vector_literal(query_embedding),
                "vtype": vector_type,
                "dbid": database_id,
                "topk": top_k,
            },
        ).mappings().all()
    return [dict(r) for r in rows]


def count() -> int:
    """向量库里的总条数。"""
    with engine.begin() as conn:
        return conn.execute(text("SELECT count(*) FROM vector_store")).scalar_one()


def _to_vector_literal(values: list[float]) -> str:
    """把 Python 列表转成 pgvector 认的字符串格式：[1.0,2.0,...]"""
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"
