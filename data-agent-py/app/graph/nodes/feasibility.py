"""可行性评估节点。

把"改写后的问题 + 召回的表结构 + 证据 + 多轮上下文"交给大模型，
让它判断这个需求属于什么类型，输出一段带标记的文本。

【为什么要有这一步】
  用户可能问"今天天气怎么样"——这种问题查数据库没意义。
  先判断类型，不合适就直接结束，省得后面白跑一趟还烧 token。

【关键：下游是条件边，靠字符串匹配决定往哪走】
  结果里包含 "【需求类型】：《数据分析》" → 继续走
  否则                                    → 直接结束
  所以 prompt 里必须要求模型输出这个标记（模板里已经写好了）。

对应 Java 的 FeasibilityAssessmentNode。
"""

import asyncio

from app.domain.schema import Schema
from app.graph.state import AgentState, StateKey
from app.llm import client, prompts


async def feasibility_node(state: AgentState) -> dict:
    rewrite_query = state.get(StateKey.REWRITE_QUERY, "")
    table_relation = state.get(StateKey.TABLE_RELATION, "")
    evidence = state.get(StateKey.EVIDENCE, "")
    multi_turn = state.get(StateKey.MULTI_TURN_CONTEXT, "(无)")

    if not table_relation or not table_relation.strip():
        raise ValueError("读不到 schema，上一个节点（table_relation）可能没跑")

    schema = Schema.model_validate_json(table_relation)

    prompt = prompts.render(
        "feasibility-assessment",
        {
            "recalled_schema": schema.build_scheme_prompt(),
            "evidence": evidence or "无",
            "canonical_query": rewrite_query,
            "multi_turn": multi_turn,
        },
    )

    result = (await asyncio.to_thread(client.chat, prompt)).strip()
    if not result:
        raise ValueError("可行性评估返回为空")

    # 顺便把判断结果打出来，方便观察条件边会往哪走
    first_line = result.splitlines()[0] if result.splitlines() else ""
    print(f"  [FEASIBILITY] 判定 → {first_line}")

    return {StateKey.FEASIBILITY_RESULT: result}
