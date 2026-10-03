"""检索演示：用一句话去向量库里捞出相关的表、列、术语、历史问答。

对应 Java 版里各节点的 retrieveXxx 方法。这是阶段 1 的"验收工具"——
后面图里的 evidence_recall / scheme_recall 节点，干的就是这件事。

用法：
    python -m scripts.search_demo "有多少学校免费餐比例超过50%"
    python -m scripts.search_demo "SAT math average score" --db california_schools
"""

import argparse

from app import settings
from app.retrieval import embeddings, vector_store
from app.retrieval.document_mapper import (
    VECTOR_TYPE_COLUMN,
    VECTOR_TYPE_GLOSSARY,
    VECTOR_TYPE_QUESTION,
    VECTOR_TYPE_TABLE,
)


def search_all(query: str, database_id: str) -> None:
    print(f"\n问题：{query}")
    print(f"库名：{database_id}")
    print("=" * 70)

    print("\n把问题转成向量...")
    query_vector = embeddings.embed_one(query)

    sections = [
        ("相关表", VECTOR_TYPE_TABLE, 5),
        ("相关列", VECTOR_TYPE_COLUMN, 8),
        ("业务术语", VECTOR_TYPE_GLOSSARY, 3),
        ("历史问答", VECTOR_TYPE_QUESTION, 3),
    ]

    for title, vector_type, top_k in sections:
        rows = vector_store.search(query_vector, database_id, vector_type, top_k)
        print(f"\n----- {title}（{len(rows)} 条）-----")
        for row in rows:
            content = " ".join(str(row["content"]).split())
            if len(content) > 80:
                content = content[:80] + "..."
            print(f"  {row['score']:.4f}  {content}")


def main() -> None:
    parser = argparse.ArgumentParser(description="向量检索演示")
    parser.add_argument("query", help="要检索的自然语言问题")
    parser.add_argument(
        "--db",
        default="california_schools",
        help="在哪个库里检索（默认 california_schools）",
    )
    args = parser.parse_args()

    if not settings.DASHSCOPE_API_KEY:
        raise SystemExit("请先在 .env 里配置 DASHSCOPE_API_KEY")

    search_all(args.query, args.db)


if __name__ == "__main__":
    main()
