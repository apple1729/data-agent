"""把 BIRD 数据集导入数据库。

对应 Java 版的 BirdSqlDatasetImportTest + DatasetEmbeddingTest。

用法：
    python -m scripts.ingest_bird                  # 全量：5 张业务表 + 向量化
    python -m scripts.ingest_bird --skip-vectors   # 只导 5 张业务表（不需要 API key）

脚本是**幂等**的：每次运行都会清空这 5 张表再重新灌，
所以可以随时重跑，不用手动清理。
"""

import argparse
import json
import logging
import uuid

from sqlalchemy import text

from app import settings
from app.db.models import (
    DbColumn,
    DbForeignKey,
    DbTable,
    GlossaryKnowledge,
    QuestionKnowledge,
)
from app.db.session import SessionLocal, engine
from app.retrieval import document_mapper, embeddings, vector_store

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-5s | %(message)s"
)
logger = logging.getLogger("ingest")

TABLES_TO_RESET = (
    "db_foreign_key",
    "db_column",
    "db_table",
    "glossary_knowledge",
    "question_knowledge",
)


def load_json(filename: str):
    """读取 data/bird 下的 JSON 文件。"""
    path = settings.DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"找不到数据文件：{path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------
# 第一步：5 张业务表
# --------------------------------------------------------------------------


def reset_tables(session) -> None:
    """清空 5 张业务表（可重复运行）。"""
    session.execute(
        text(
            "TRUNCATE "
            + ", ".join(TABLES_TO_RESET)
            + " RESTART IDENTITY CASCADE"
        )
    )
    session.commit()
    logger.info("已清空 5 张业务表")


def _primary_key_indexes(bird_db: dict) -> set[int]:
    """BIRD 的 primary_keys 里元素可能是整数，也可能是数组（联合主键），
    这里统一压平成一个集合。"""
    indexes: set[int] = set()
    for pk in bird_db.get("primary_keys") or []:
        if isinstance(pk, list):
            indexes.update(int(x) for x in pk)
        else:
            indexes.add(int(pk))
    return indexes


def ingest_schema(session) -> None:
    """dev_tables.json → db_table / db_column / db_foreign_key"""
    databases = load_json("dev_tables.json")
    logger.info("读到 %d 个数据库的 schema", len(databases))

    total_tables = total_columns = 0
    # (databaseId, 表名, 列名) -> DbColumn，最后用来解析外键
    column_index: dict[tuple[str, str, str], DbColumn] = {}

    for bird_db in databases:
        database_id = bird_db["db_id"]
        table_names_original = bird_db["table_names_original"]
        table_names = bird_db.get("table_names") or []
        column_names_original = bird_db["column_names_original"]
        column_names = bird_db.get("column_names") or []
        column_types = bird_db.get("column_types") or []
        pk_indexes = _primary_key_indexes(bird_db)

        table_objects: list[DbTable] = []

        for table_index, table_name in enumerate(table_names_original):
            # description 用 BIRD 的"可读表名"（带空格），它才是拿去算向量的文本
            table_desc = (
                table_names[table_index]
                if table_index < len(table_names)
                else table_name
            )
            table = DbTable(
                id=uuid.uuid4(),
                name=table_name,
                description=table_desc,
                database_id=database_id,
            )
            session.add(table)
            table_objects.append(table)

            # 第 0 条列名是占位用的 [-1, "*"]，靠 owner 判断自动跳过
            for column_index_, info in enumerate(column_names_original):
                if not isinstance(info, list) or len(info) < 2:
                    continue
                owner_index, column_name = info[0], info[1]
                if owner_index != table_index:
                    continue
                if not isinstance(column_name, str) or not column_name:
                    continue

                readable = (
                    column_names[column_index_][1]
                    if column_index_ < len(column_names)
                    and isinstance(column_names[column_index_], list)
                    and len(column_names[column_index_]) >= 2
                    else column_name
                )
                column = DbColumn(
                    id=uuid.uuid4(),
                    name=column_name,
                    type=column_types[column_index_]
                    if column_index_ < len(column_types)
                    else "",
                    description=readable,
                    is_primary_key=column_index_ in pk_indexes,
                    table_id=table.id,
                )
                session.add(column)
                column_index[(database_id, table_name, column_name)] = column
                total_columns += 1

        total_tables += len(table_objects)
        session.flush()  # 让自增/外键依赖的 id 落地
        logger.info("  %-28s 表 %2d 张", database_id, len(table_objects))

    # 外键：BIRD 里存的是"列下标对"，要先换成 (表名, 列名) 再查到 DbColumn
    total_fks = 0
    for bird_db in databases:
        database_id = bird_db["db_id"]
        table_names_original = bird_db["table_names_original"]
        column_names_original = bird_db["column_names_original"]

        for pair in bird_db.get("foreign_keys") or []:
            if not isinstance(pair, list) or len(pair) < 2:
                continue
            source_index, target_index = int(pair[0]), int(pair[1])
            if not (
                0 <= source_index < len(column_names_original)
                and 0 <= target_index < len(column_names_original)
            ):
                continue

            source_info = column_names_original[source_index]
            target_info = column_names_original[target_index]
            source_table = table_names_original[source_info[0]]
            target_table = table_names_original[target_info[0]]

            source_column = column_index.get((database_id, source_table, source_info[1]))
            target_column = column_index.get((database_id, target_table, target_info[1]))
            if source_column is None or target_column is None:
                continue

            session.add(
                DbForeignKey(
                    id=uuid.uuid4(),
                    source_column_id=source_column.id,
                    target_column_id=target_column.id,
                )
            )
            total_fks += 1

    session.commit()
    logger.info(
        "业务表导入完成：表 %d 张 / 列 %d 个 / 外键 %d 条",
        total_tables,
        total_columns,
        total_fks,
    )


def ingest_knowledge(session) -> None:
    """dev.json → glossary_knowledge + question_knowledge"""
    questions = load_json("dev.json")
    logger.info("读到 %d 道问题", len(questions))

    # 1) evidence 去重后进 glossary_knowledge（BIRD 没有术语名，term 存空串）
    seen_evidence: set[str] = set()
    glossary_count = 0
    for item in questions:
        evidence = (item.get("evidence") or "").strip()
        if not evidence or evidence in seen_evidence:
            continue
        seen_evidence.add(evidence)
        session.add(
            GlossaryKnowledge(
                id=uuid.uuid4(),
                database_id=item["db_id"],
                term="",
                description=evidence,
                synonyms=None,
            )
        )
        glossary_count += 1

    # 2) 问题 + 标准 SQL 全量进 question_knowledge
    for item in questions:
        session.add(
            QuestionKnowledge(
                id=uuid.uuid4(),
                database_id=item["db_id"],
                question=item["question"],
                answer=item["SQL"],
            )
        )

    session.commit()
    logger.info(
        "知识导入完成：术语 %d 条 / 历史问答 %d 条（evidence 去重后）",
        glossary_count,
        len(questions),
    )


# --------------------------------------------------------------------------
# 第二步：向量化入库
# --------------------------------------------------------------------------


def build_vector_documents(session) -> list[document_mapper.VectorDocument]:
    """把四类实体都转成待向量化的文档，顺序固定。"""
    docs: list[document_mapper.VectorDocument] = []

    tables = session.query(DbTable).all()
    docs.extend(document_mapper.from_table(t) for t in tables)
    logger.info("表文档 %d 条", len(tables))

    columns = session.query(DbColumn).all()
    table_by_id = {t.id: t for t in tables}
    column_docs = [
        document_mapper.from_column(c, table_by_id[c.table_id])
        for c in columns
        if c.table_id in table_by_id
    ]
    docs.extend(column_docs)
    logger.info("列文档 %d 条", len(column_docs))

    glossaries = session.query(GlossaryKnowledge).all()
    docs.extend(document_mapper.from_glossary(g) for g in glossaries)
    logger.info("术语文档 %d 条", len(glossaries))

    questions = session.query(QuestionKnowledge).all()
    docs.extend(document_mapper.from_question(q) for q in questions)
    logger.info("问答文档 %d 条", len(questions))

    return docs


def ingest_vectors(session) -> None:
    """向量化并写入 vector_store。"""
    vector_store.init_schema()
    logger.info("vector_store 表已就绪")

    docs = build_vector_documents(session)
    if not docs:
        logger.warning("没有可向量化的内容，先跑不带 --skip-vectors 的导入")
        return

    batch_size = settings.EMBEDDING_BATCH_SIZE
    total = len(docs)
    logger.info("共 %d 条待向量化，每批 %d 条，预计 %d 批",
                total, batch_size, (total + batch_size - 1) // batch_size)

    for start in range(0, total, batch_size):
        batch = docs[start : start + batch_size]
        vectors = embeddings.embed_texts([d.text for d in batch])
        vector_store.add_documents(batch, vectors)
        done = min(start + batch_size, total)
        if done % 200 == 0 or done == total:
            logger.info("  向量化进度 %d / %d", done, total)

    logger.info("向量化完成，vector_store 现有 %d 条", vector_store.count())


# --------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="把 BIRD 数据集导入数据库")
    parser.add_argument(
        "--skip-vectors",
        action="store_true",
        help="只导入 5 张业务表，跳过向量化（不需要 DASHSCOPE_API_KEY）",
    )
    args = parser.parse_args()

    session = SessionLocal()
    try:
        reset_tables(session)
        ingest_schema(session)
        ingest_knowledge(session)

        if args.skip_vectors:
            logger.info("已跳过向量化（--skip-vectors）")
        else:
            ingest_vectors(session)
    finally:
        session.close()


if __name__ == "__main__":
    main()
