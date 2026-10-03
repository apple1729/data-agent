"""表结构召回节点。

真实现要做的（阶段 3）：
  用改写后的 query 去向量库做两路检索——
    vectorType=table  取表级 schema（topK=10）
    vectorType=column 取列级 schema（topK=30）
  这只是"粗筛"，精挑交给下一个节点。

对应 Java 的 SchemeReCallNode（注意类名拼写）。
"""

from app.graph.state import AgentState, StateKey


async def scheme_recall_node(state: AgentState) -> dict:
    query = state.get(StateKey.REWRITE_QUERY, "")
    print(f"  [SCHEME_RECALL] 用 query 检索表结构：{query!r}")

    return {
        StateKey.TABLE_SCHEME: [{"table": "假表1"}, {"table": "假表2"}],
        StateKey.COLUMN_SCHEME: [{"column": "假列1"}, {"column": "假列2"}],
    }
