"""任务规划节点。

真实现要做的（阶段 3）：
  让 LLM 输出一份结构化的执行计划（Plan 对象），供人工审核展示。
  注意在 Supervisor 架构下它只是"草稿计划"，真正的逐步派单交给 Supervisor。

对应 Java 的 PlannerNode。
"""

from app.graph.state import AgentState, StateKey


async def planner_node(state: AgentState) -> dict:
    feedback = state.get(StateKey.CONFIRMATION_FEEDBACK, "")
    note = f"（用户反馈：{feedback}）" if feedback else ""
    print(f"  [PLANNER] 生成计划{note}")

    return {
        StateKey.PLAN: (
            '{"steps": [{"step": 1, "action": "[假] 查数据"}, '
            '{"step": 2, "action": "[假] 写报告"}]}'
        )
    }
