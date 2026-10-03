"""报告生成节点。

真实现要做的（阶段 3）：
  把前面所有步骤的结果汇总，生成一份面向用户的 Markdown 报告。
  这是流水线的终点。

对应 Java 的 ReportGeneratorNode。
"""

from app.graph.state import AgentState, StateKey


async def report_generator_node(state: AgentState) -> dict:
    results = state.get(StateKey.EXECUTION_OUTPUT, {})
    print(f"  [REPORT_GENERATOR] 汇总 {len(results)} 份结果，生成报告")

    return {
        StateKey.REPORT_RESULT: (
            "# [假] 分析报告\n\n"
            f"本报告汇总了 {len(results)} 个步骤的结果。\n\n"
            "阶段 3 会换成 LLM 根据真实数据生成。"
        )
    }
