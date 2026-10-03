"""主管调度节点。

真实现要做的（阶段 3）：
  每一轮让 LLM 看"用户问题 + 历次执行结果"，决定下一步派给谁：
    派 SQL / 派 Python / 派报告 / 收工
  并把结果汇总、轮次 +1（用于熔断，防止死循环）。

阶段 2 用一个固定的假策略代替：
  第 0 轮 → 派 SQL
  第 1 轮 → 派 Python
  第 2 轮 → 派报告
  第 3 轮 → 收工
这样能一次走遍所有子 Agent 的节点，方便验证图连线对不对。

对应 Java 的 SupervisorNode + SupervisorEdge。
"""

from app.graph.node_names import GraphNode
from app.graph.state import AgentState, StateKey

# 假的派单策略：轮次 → 下一个节点
FAKE_DISPATCH = {
    0: GraphNode.SQL_GENERATION,
    1: GraphNode.PYTHON_GENERATION,
    2: GraphNode.REPORT_GENERATION,
}
MAX_ITERATION = 3   # 熔断上限：超过就收工


async def supervisor_node(state: AgentState) -> dict:
    iteration = state.get(StateKey.SUPERVISOR_ITERATION, 0)
    next_node = FAKE_DISPATCH.get(iteration, "__END__")

    if iteration >= MAX_ITERATION:
        print(f"  [SUPERVISOR] 第 {iteration} 轮 → 已达上限，收工")
        next_node = "__END__"
    else:
        print(f"  [SUPERVISOR] 第 {iteration} 轮 → 派给 {next_node}")

    return {
        StateKey.NEXT_NODE: next_node,
        StateKey.CURRENT_STEP: iteration + 1,
        StateKey.SUPERVISOR_ITERATION: iteration + 1,
    }
