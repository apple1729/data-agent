"""任务规划节点。

让大模型把问题拆解成一份结构化的执行计划。

**注意它在整个架构里的定位**：
  在 Supervisor（主管调度）架构下，这个节点输出的是**草稿计划**——
  主要用途是给人工审核那一站展示给用户看。
  真正的逐步派单交给后面的 Supervisor 节点动态决定，
  执行时并不严格照这份计划的步骤走。

【输出存的是原始文本】
  和 Java 一样，这个节点把模型返回的**原文**存进状态，
  不存解析后的对象。因为后面 Supervisor 会自己解析一遍。
  这里解析只是为了打日志、确认格式没崩。

对应 Java 的 PlannerNode。
"""

import asyncio
import logging

from app.domain.schema import Schema
from app.graph.state import AgentState, StateKey
from app.llm import client, prompts, structured
from app.llm.dto import Plan

logger = logging.getLogger(__name__)


async def planner_node(state: AgentState) -> dict:
    rewrite_query = state.get(StateKey.REWRITE_QUERY, "")
    table_relation = state.get(StateKey.TABLE_RELATION, "")
    evidence = state.get(StateKey.EVIDENCE, "")
    feedback = state.get(StateKey.CONFIRMATION_FEEDBACK, "")

    if not table_relation or not table_relation.strip():
        raise ValueError("读不到 schema，上一个节点（table_relation）可能没跑")
    schema = Schema.model_validate_json(table_relation)

    # semantic_model 是"语义层模型"（指标口径之类），原项目留空没做
    prompt = prompts.render(
        "planner",
        {
            "user_question": rewrite_query,
            "schema": schema.build_scheme_prompt(),
            "evidence": evidence or "无",
            "semantic_model": "",
            "plan_validation_error": feedback,
            "format": structured.format_hint(Plan),
        },
    )

    plan_text = (await asyncio.to_thread(client.chat, prompt)).strip()
    if not plan_text:
        raise ValueError("计划生成为空")

    # 尝试解析一遍只为打日志——**解析失败也不能让图崩**，
    # 因为存进状态的是原文，真正用它的是 Supervisor（那边有兜底逻辑）。
    # 注意：要读 tool_parameters 里的字段，不是顶层那个同名字段！
    #   Java 里 SqlGeneratorNode / ReportGeneratorNode / SupervisorNode
    #   读的全是 getToolParameters().getXxx()，顶层那套同名属性从来没被读过，
    #   属于早期设计的遗留。模型也倾向于把内容填进 tool_parameters。
    try:
        plan = structured.parse(plan_text, Plan)
        print(f"  [PLANNER] 生成计划 {len(plan.execution_plan)} 步：")
        for step in plan.execution_plan:
            params = step.tool_parameters
            brief = (params.instruction or params.summary_and_recommendations or "")
            print(f"      {step.step}. {step.tool_to_use} — {brief[:60]}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("计划格式解析失败（不影响流程，原文已存入状态）: %s", exc)
        print(f"  [PLANNER] 计划已生成，但格式有瑕疵（{type(exc).__name__}），原文存入状态")

    return {StateKey.PLAN: plan_text}
