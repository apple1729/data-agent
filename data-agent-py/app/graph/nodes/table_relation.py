"""表关系推理节点（Schema Linking）。

**13 个节点里最复杂的一个。** 做四件事：

  1. 【自适应阈值选表】
     上一个节点召回的表和列各带一个相似度分数。分数是浮动的，
     写死一个阈值不行——所以从 0.4 起步，逐步往上试，
     挑出"选出来的表数量最接近 4 张"的那个阈值。

  2. 【外键扩展】
     光靠语义召回容易漏掉"桥表"。比如查订单和用户，
     可能需要商品表来搭桥。所以把跟已选表有外键关系的表全补进来。

  3. 【让大模型做最终裁剪】
     候选表可能有七八张，全塞给后续节点太浪费 token。
     把候选表的结构给它，让它挑出真正要用的几张。

  4. 【输出 Schema JSON】
     注意输出的是 **JSON 字符串**，不是对象——
     因为状态里存的就是字符串，下游节点要 json.loads 它。

对应 Java 的 TableRelationNode。
"""

import asyncio
import json

from app.graph.state import AgentState, StateKey
from app.db import schema_repo
from app.domain.schema import (
    DbColumnView,
    DbForeignKeyView,
    DbTableView,
    ForeignKeyColumnView,
    ForeignKeyTableView,
    Schema,
)
from app.llm import client, prompts

# 自适应阈值的起点，和目标保留的表数量（照抄 Java）
BASE_HIGH_SIMILARITY_THRESHOLD = 0.4
TARGET_TABLE_COUNT = 4


async def table_relation_node(state: AgentState) -> dict:
    database_id = state.get(StateKey.DATABASE_ID, "")
    rewrite_query = state.get(StateKey.REWRITE_QUERY, "")
    evidence = state.get(StateKey.EVIDENCE, "")
    table_docs = state.get(StateKey.TABLE_SCHEME, []) or []
    column_docs = state.get(StateKey.COLUMN_SCHEME, []) or []

    # ---- 1) 从向量召回结果里把分数抽出来 ----
    table_scores: dict[str, float] = {}
    for doc in table_docs:
        table_id = (doc.get("metadata") or {}).get("tableId")
        score = doc.get("score")
        if table_id and score is not None:
            # 同一张表可能被召回多次，取最高分
            table_scores[table_id] = max(table_scores.get(table_id, 0.0), float(score))

    column_scores: list[tuple[str, str, float]] = []   # (tableId, columnId, score)
    for doc in column_docs:
        meta = doc.get("metadata") or {}
        table_id, column_id, score = meta.get("tableId"), meta.get("columnId"), doc.get("score")
        if table_id and column_id and score is not None:
            column_scores.append((table_id, column_id, float(score)))

    # ---- 2) 自适应阈值选表 ----
    selection = _select_threshold(table_scores, column_scores)
    print(
        f"  [TABLE_RELATION] 阈值={selection.threshold:.2f} "
        f"选出 {len(selection.table_ids)} 张表（表召回 {len(table_scores)} / 列召回 {len(column_scores)}）"
    )

    # ---- 3) 外键扩展 ----
    foreign_keys = await asyncio.to_thread(
        schema_repo.find_foreign_keys_by_database, database_id
    )
    related_fks = [fk for fk in foreign_keys if _has_any_table(fk, selection.table_ids)]

    merged_table_ids = list(selection.table_ids)
    for fk in related_fks:
        for col in (fk.source_column, fk.target_column):
            if col.table_id not in merged_table_ids:
                merged_table_ids.append(col.table_id)

    # 外键涉及的列也要保留（否则 join 用的列被裁掉就废了）
    fk_column_ids_by_table: dict[str, set[str]] = {}
    for fk in related_fks:
        for col in (fk.source_column, fk.target_column):
            fk_column_ids_by_table.setdefault(str(col.table_id), set()).add(str(col.id))

    print(f"  [TABLE_RELATION] 外键扩展后候选表 {len(merged_table_ids)} 张")

    # ---- 4) 取表结构，拼给大模型看的 schema 文字 ----
    tables = await asyncio.to_thread(
        schema_repo.find_tables_with_columns, merged_table_ids
    )
    candidate_views = [
        _to_table_view(
            table,
            keep_column_ids=(
                selection.column_ids_by_table.get(str(table.id), set())
                | fk_column_ids_by_table.get(str(table.id), set())
            ),
        )
        for table in tables
    ]
    schema_info = Schema(
        databaseId=database_id,
        dbTables=candidate_views,
        dbForeignKeys=[_to_fk_view(fk) for fk in related_fks],
    ).build_scheme_prompt()

    # ---- 5) 让大模型做最终裁剪 ----
    prompt = prompts.render(
        "mix-selector",
        {"schema_info": schema_info, "question": rewrite_query, "evidence": evidence},
    )
    raw = await asyncio.to_thread(client.chat, prompt)
    filter_table_names = _parse_table_names(raw)
    print(f"  [TABLE_RELATION] 大模型最终选定 {len(filter_table_names)} 张表：{filter_table_names}")

    # ---- 6) 按最终表名取表和外键 ----
    final_tables = await asyncio.to_thread(
        schema_repo.find_tables_by_database_and_names, database_id, filter_table_names
    )
    name_set = set(filter_table_names)
    final_fks = [
        fk
        for fk in foreign_keys
        if fk.source_column.table.name in name_set or fk.target_column.table.name in name_set
    ]

    final_schema = Schema(
        databaseId=database_id,
        dbTables=[_to_table_view(t) for t in final_tables],
        dbForeignKeys=[_to_fk_view(fk) for fk in final_fks],
    )
    return {StateKey.TABLE_RELATION: final_schema.model_dump_json()}


# ---------------------------------------------------------------------------
# 视图转换
# ---------------------------------------------------------------------------


def _to_column_view(column) -> DbColumnView:
    return DbColumnView(
        name=column.name,
        type=column.type,
        description=column.description,
        isPrimaryKey=column.is_primary_key,
    )


def _to_table_view(table, keep_column_ids: set[str] | None = None) -> DbTableView:
    """把数据库实体转成视图对象。

    keep_column_ids 非空时只保留这些列（外键扩展阶段用：
    只需要"语义命中的列"和"外键用到的列"，其余裁掉省 token）。

    这里**不去改 ORM 对象的 columns**，而是新建视图——
    改 ORM 对象在 session 已关闭的情况下容易出问题。
    """
    columns = list(table.columns)
    if keep_column_ids:
        columns = [c for c in columns if str(c.id) in keep_column_ids]
    return DbTableView(name=table.name, columns=[_to_column_view(c) for c in columns])


def _to_fk_view(foreign_key) -> DbForeignKeyView:
    return DbForeignKeyView(
        sourceColumn=ForeignKeyColumnView(
            name=foreign_key.source_column.name,
            dbTable=ForeignKeyTableView(name=foreign_key.source_column.table.name),
        ),
        targetColumn=ForeignKeyColumnView(
            name=foreign_key.target_column.name,
            dbTable=ForeignKeyTableView(name=foreign_key.target_column.table.name),
        ),
    )


def _has_any_table(foreign_key, table_ids: list[str]) -> bool:
    return (
        str(foreign_key.source_column.table_id) in table_ids
        or str(foreign_key.target_column.table_id) in table_ids
    )


# ---------------------------------------------------------------------------
# 自适应阈值
# ---------------------------------------------------------------------------


class _Selection:
    """一次阈值试验的结果。"""

    def __init__(self, threshold, table_ids, column_ids_by_table):
        self.threshold = threshold
        self.table_ids = table_ids
        self.column_ids_by_table = column_ids_by_table


def _build_selection(threshold, table_scores, column_scores) -> _Selection:
    """按给定阈值挑表。逻辑照抄 Java 的 buildSelection()。"""
    # 每张表取它所有被召回列里的最高分
    table_score_from_column: dict[str, float] = {}
    for table_id, _column_id, score in column_scores:
        table_score_from_column[table_id] = max(
            table_score_from_column.get(table_id, 0.0), score
        )

    high_table_ids = [tid for tid, score in table_scores.items() if score >= threshold]
    high_columns = [c for c in column_scores if c[2] >= threshold]
    high_column_table_ids = list(dict.fromkeys(c[0] for c in high_columns))

    column_ids_by_table: dict[str, set[str]] = {}
    for table_id, column_id, _score in high_columns:
        column_ids_by_table.setdefault(table_id, set()).add(column_id)

    # 表级命中和列级命中的表合并（保持顺序 + 去重）
    selected = list(dict.fromkeys(high_table_ids + high_column_table_ids))

    # 阈值太高导致一张都没选中时，至少各留一个最高分的
    if not selected:
        if table_scores:
            selected.append(max(table_scores.items(), key=lambda kv: kv[1])[0])
        if table_score_from_column:
            selected.append(max(table_score_from_column.items(), key=lambda kv: kv[1])[0])

    return _Selection(threshold, selected, column_ids_by_table)


def _select_threshold(table_scores, column_scores) -> _Selection:
    """挑一个让候选表数量最接近 4 张的阈值。

    为什么不写死阈值：不同问题的分数分布不一样，写死的阈值
    有时候选出 10 张表（太多），有时候一张都不选。所以从 0.4 起步，
    每次加 0.01 往上试，看哪个阈值选出的表数最接近目标。
    """
    best = _build_selection(
        BASE_HIGH_SIMILARITY_THRESHOLD, table_scores, column_scores
    )
    if len(best.table_ids) <= TARGET_TABLE_COUNT:
        return best

    for i in range(1, 30):
        threshold = min(BASE_HIGH_SIMILARITY_THRESHOLD + i * 0.01, 0.99)
        candidate = _build_selection(threshold, table_scores, column_scores)
        candidate_diff = abs(TARGET_TABLE_COUNT - len(candidate.table_ids))
        best_diff = abs(TARGET_TABLE_COUNT - len(best.table_ids))
        if candidate_diff < best_diff or (
            candidate_diff == best_diff and candidate.threshold > best.threshold
        ):
            best = candidate
    return best


# ---------------------------------------------------------------------------
# 解析大模型返回的表名列表
# ---------------------------------------------------------------------------


def _parse_table_names(text: str) -> list[str]:
    """模型应该返回一个 JSON 数组，比如 ["frpm", "schools"]。"""
    value = (text or "").strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1]
        value = value.rsplit("```", 1)[0]
    start, end = value.find("["), value.rfind("]")
    if start >= 0 and end > start:
        value = value[start : end + 1]
    names = json.loads(value)
    return list(dict.fromkeys(n for n in names if isinstance(n, str) and n.strip()))
