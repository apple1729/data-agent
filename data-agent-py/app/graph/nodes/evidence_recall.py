"""证据召回节点。

真实现要做的（阶段 3）：
  1. 用 LLM 把"多轮上下文 + 用户最新问题"改写成一句独立完整的问句
  2. 拿这句去向量库召回两类东西：业务术语、历史问答
  3. 历史问答只存了问题，还要回 question_knowledge 表取完整问答
  4. 拼成一段 Evidence 文本

对应 Java 的 EvidenceRecallNode。
"""

from app.graph.state import AgentState, StateKey


async def evidence_recall_node(state: AgentState) -> dict:
    user_input = state.get(StateKey.USER_INPUT, "")
    database_id = state.get(StateKey.DATABASE_ID, "")
    print(f"  [EVIDENCE_RECALL] 输入={user_input!r} 库={database_id}")

    return {
        StateKey.REWRITE_QUERY: f"[假] 改写后的独立问句：{user_input}",
        StateKey.EVIDENCE: "[假] 业务术语 + 历史问答（阶段 3 从向量库真取）",
    }
