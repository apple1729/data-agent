"""3 个条件边。

对应 Java 版的 FeasibilityAssessmentEdge / HumanFeedbackEdge / SupervisorEdge。

【普通边 vs 条件边】
  普通边：干完 A 一定去 B。      add_edge(A, B)
  条件边：看情况决定去哪。        add_conditional_edges(A, 判断函数, 映射表)

【条件边函数要返回什么】
  返回一个"路标"，再由 builder 里的映射表翻译成真正的下一个节点。
  这种"两步走"的好处是：判断逻辑（这里）和连线关系（builder）分开，
  看代码时不用来回跳。
"""

from app.graph.node_names import GraphNode
from app.graph.state import AgentState, StateKey


def feasibility_edge(state: AgentState) -> str:
    """可行性评估之后往哪走。

    判定依据是节点输出的文本里有没有那个标记——这是原项目的做法
    （用字符串匹配而不是结构化字段，有点糙，但保持一致）。
    """
    result = state.get(StateKey.FEASIBILITY_RESULT, "")
    if "【需求类型】：《数据分析》" in result:
        return GraphNode.PLANNER       # 能做 → 去做计划
    return "__END__"                   # 做不了 → 直接结束


def human_feedback_edge(state: AgentState) -> str:
    """人工审核之后往哪走。

    真正的判断（批准/拒绝/熔断）在 human_feedback 节点里做完了，
    这里只负责把那个结果读出来当路标。
    """
    return state.get(StateKey.HUMAN_NEXT_NODE, "__END__")


def supervisor_edge(state: AgentState) -> str:
    """主管派活之后往哪走。

    同理，派单决策在 supervisor 节点里做完了，这里只读结果。
    """
    return state.get(StateKey.NEXT_NODE, "__END__")
