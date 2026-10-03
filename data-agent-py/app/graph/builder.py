"""图的装配：把 13 个节点和条件边连成一张图。

对应 Java 版的 GraphConfiguration#dataAgentMainGraph。

【整体形状】
    召回段（一条直线，走完不回头）：
      START → 证据召回 → 表结构召回 → 表关系推理 → 可行性评估
                                                        ↓ 条件边
                                            【不能分析】→ END
                                                        ↓
    规划段（一条直线）：
      做计划 → 人工审核 ──条件边──【拒绝】→ 回到做计划
                        └─【批准/熔断】→ 主管调度 或 END

    执行段（围着主管转圈）：
      主管调度 ──条件边──┬→ 生成SQL → 执行SQL ──────────┐
                        ├→ 生成Python → 执行 → 解读 ──┤ 每轮干完
                        ├→ 生成报告 → END              │ 都回到主管
                        └→ END                         │
                        ↑______________________________|
"""

from langgraph.graph import END, START, StateGraph

from app.graph.edges import feasibility_edge, human_feedback_edge, supervisor_edge
from app.graph.node_names import END_ARTIFACT_NAME, GraphNode
from app.graph.nodes import (
    evidence_recall_node,
    feasibility_node,
    human_feedback_node,
    planner_node,
    python_analyze_node,
    python_execute_node,
    python_generator_node,
    report_generator_node,
    scheme_recall_node,
    sql_execute_node,
    sql_generator_node,
    supervisor_node,
    table_relation_node,
)
from app.graph.state import AgentState


def build_graph() -> StateGraph:
    """装配图（还没编译）。"""
    graph = StateGraph(AgentState)

    # ---------- 1) 注册 13 个节点 ----------
    graph.add_node(GraphNode.EVIDENCE_RECALL, evidence_recall_node)
    graph.add_node(GraphNode.SCHEMA_RECALL, scheme_recall_node)
    graph.add_node(GraphNode.TABLE_RELATION, table_relation_node)
    graph.add_node(GraphNode.FEASIBILITY_ASSESSMENT, feasibility_node)
    graph.add_node(GraphNode.PLANNER, planner_node)

    graph.add_node(GraphNode.HUMAN_FEEDBACK, human_feedback_node)
    graph.add_node(GraphNode.SUPERVISOR, supervisor_node)
    graph.add_node(GraphNode.SQL_GENERATION, sql_generator_node)
    graph.add_node(GraphNode.SQL_EXECUTION, sql_execute_node)
    graph.add_node(GraphNode.PYTHON_GENERATION, python_generator_node)
    
    graph.add_node(GraphNode.PYTHON_EXECUTION, python_execute_node)
    graph.add_node(GraphNode.PYTHON_ANALYSIS, python_analyze_node)
    graph.add_node(GraphNode.REPORT_GENERATION, report_generator_node)

    # ---------- 2) 召回段：一条直线 ----------
    graph.add_edge(START, GraphNode.EVIDENCE_RECALL)
    graph.add_edge(GraphNode.EVIDENCE_RECALL, GraphNode.SCHEMA_RECALL)
    graph.add_edge(GraphNode.SCHEMA_RECALL, GraphNode.TABLE_RELATION)
    graph.add_edge(GraphNode.TABLE_RELATION, GraphNode.FEASIBILITY_ASSESSMENT)

    # ---------- 3) 条件边一：能做数据分析吗 ----------
    graph.add_conditional_edges(
        GraphNode.FEASIBILITY_ASSESSMENT,
        feasibility_edge,
        {
            GraphNode.PLANNER: GraphNode.PLANNER,   # 能做 → 去做计划
            END_ARTIFACT_NAME: END,                 # 做不了 → 收工
        },
    )

    # ---------- 4) 规划段 ----------
    graph.add_edge(GraphNode.PLANNER, GraphNode.HUMAN_FEEDBACK)

    # ---------- 5) 条件边二：人工审核后去哪 ----------
    graph.add_conditional_edges(
        GraphNode.HUMAN_FEEDBACK,
        human_feedback_edge,
        {
            GraphNode.SUPERVISOR: GraphNode.SUPERVISOR,   # 批准 → 去干活
            GraphNode.PLANNER: GraphNode.PLANNER,         # 拒绝 → 重新做计划
            END_ARTIFACT_NAME: END,                       # 返工超限 → 收工
        },
    )

    # ---------- 6) 条件边三：主管派活 ----------
    graph.add_conditional_edges(
        GraphNode.SUPERVISOR,
        supervisor_edge,
        {
            GraphNode.SQL_GENERATION: GraphNode.SQL_GENERATION,
            GraphNode.PYTHON_GENERATION: GraphNode.PYTHON_GENERATION,
            GraphNode.REPORT_GENERATION: GraphNode.REPORT_GENERATION,
            END_ARTIFACT_NAME: END,
        },
    )

    # ---------- 7) 执行段的固定连线 ----------
    graph.add_edge(GraphNode.SQL_GENERATION, GraphNode.SQL_EXECUTION)
    graph.add_edge(GraphNode.SQL_EXECUTION, GraphNode.SUPERVISOR)     # 干完回主管
    graph.add_edge(GraphNode.PYTHON_GENERATION, GraphNode.PYTHON_EXECUTION)
    graph.add_edge(GraphNode.PYTHON_EXECUTION, GraphNode.PYTHON_ANALYSIS)
    graph.add_edge(GraphNode.PYTHON_ANALYSIS, GraphNode.SUPERVISOR)   # 干完回主管
    graph.add_edge(GraphNode.REPORT_GENERATION, END)

    return graph


def compile_graph():
    """编译成可执行的图。

    阶段 5 会在这里加 checkpointer（断点存储）和 interrupt_before
    （在人工审核节点前中断），现在先不加。
    """
    return build_graph().compile()
