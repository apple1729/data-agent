"""表关系推理节点（Schema Linking）。

**13 个节点里最复杂的一个。** 真实现要做的（阶段 3）：
  1. 合并表级/列级召回结果，按相似度自适应选一个阈值，目标留下 4 张表
  2. 查外键，把"桥表/连接表"补进来
  3. 把候选表的结构给 LLM，让它做最后一次裁剪
  4. 输出一个 Schema 对象的 JSON 字符串（下游节点要 json.loads 它）

对应 Java 的 TableRelationNode。
"""

import json

from app.graph.state import AgentState, StateKey


async def table_relation_node(state: AgentState) -> dict:
    database_id = state.get(StateKey.DATABASE_ID, "")
    tables = state.get(StateKey.TABLE_SCHEME, [])
    print(f"  [TABLE_RELATION] 候选表 {len(tables)} 个，开始精选（库={database_id}）")

    # 真实现输出的是 Schema 对象的 JSON 字符串，这里先给个同构的假壳，
    # 免得阶段 3 替换时下游节点的解析逻辑要跟着改。
    fake_schema = {
        "databaseId": database_id,
        "dbTables": [{"name": "假表", "columns": [{"name": "假列", "type": "text"}]}],
        "dbForeignKeys": [],
    }
    return {StateKey.TABLE_RELATION: json.dumps(fake_schema, ensure_ascii=False)}
