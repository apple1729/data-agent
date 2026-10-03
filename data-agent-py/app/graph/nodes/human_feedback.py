"""人工审核节点。

真实现要做的（阶段 5）：
  这是整张图的**中断点**。图跑到这里会停下来，把计划展示给用户，
  等回话：
    批准 → 去 SUPERVISOR
    拒绝 → 回 PLANNER 重新规划，返工次数 +1
    返工 >= 3 次 → 直接结束（熔断）

阶段 2 先不做中断，默认当作"用户已批准"，让流程能一路走完。

对应 Java 的 HumanFeedbackNode。
"""

from app.graph.node_names import GraphNode
from app.graph.state import AgentState, StateKey


async def human_feedback_node(state: AgentState) -> dict:
    count = state.get(StateKey.REPAIR_COUNT, 1)
    print(f"  [HUMAN_FEEDBACK] 计划待审核（返工次数={count}），阶段 2 默认批准")

    # 阶段 5 会在这里改成：停下来等用户回话
    return {StateKey.HUMAN_NEXT_NODE: GraphNode.SUPERVISOR}
