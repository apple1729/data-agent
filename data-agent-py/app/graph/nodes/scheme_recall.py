"""表结构召回节点。

用改写后的 query 去向量库做两路检索（**纯检索，不调大模型**）：
    vectorType=table  取表级 schema（topK=10）
    vectorType=column 取列级 schema（topK=30）

这只是"粗筛"——把可能相关的表和列捞出来，精挑细选交给下一个节点
（table_relation）处理。

对应 Java 的 SchemeReCallNode（注意类名拼写）。
"""

import asyncio

from app.graph.state import AgentState, StateKey
from app.retrieval import vector_store
from app.retrieval.document_mapper import VECTOR_TYPE_COLUMN, VECTOR_TYPE_TABLE

# 条数照抄 Java：表取 10 个，列取 30 个
TABLE_TOP_K = 10
COLUMN_TOP_K = 30


async def scheme_recall_node(state: AgentState) -> dict:
    rewrite_query = state.get(StateKey.REWRITE_QUERY, "")
    database_id = state.get(StateKey.DATABASE_ID, "")

    if not rewrite_query:
        print("  [SCHEME_RECALL] 没有 query，跳过")
        return {StateKey.TABLE_SCHEME: [], StateKey.COLUMN_SCHEME: []}

    # search_by_text 内部要调 embedding 接口（同步网络请求），
    # 用 to_thread 丢到线程池里跑，避免阻塞事件循环。
    tables = await asyncio.to_thread(
        vector_store.search_by_text,
        rewrite_query,
        database_id,
        VECTOR_TYPE_TABLE,
        TABLE_TOP_K,
    )
    columns = await asyncio.to_thread(
        vector_store.search_by_text,
        rewrite_query,
        database_id,
        VECTOR_TYPE_COLUMN,
        COLUMN_TOP_K,
    )

    print(f"  [SCHEME_RECALL] 召回：表 {len(tables)} 个 / 列 {len(columns)} 个")

    return {
        StateKey.TABLE_SCHEME: tables,
        StateKey.COLUMN_SCHEME: columns,
    }
