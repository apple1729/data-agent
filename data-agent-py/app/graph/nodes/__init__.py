"""13 个节点。

每个节点是一个 async 函数：读 state → 干活 → 返回一个 dict（要更新的字段）。
阶段 2 全都是空壳，阶段 3 逐个填真逻辑。
"""

from app.graph.nodes.evidence_recall import evidence_recall_node
from app.graph.nodes.feasibility import feasibility_node
from app.graph.nodes.human_feedback import human_feedback_node
from app.graph.nodes.planner import planner_node
from app.graph.nodes.python_analyze import python_analyze_node
from app.graph.nodes.python_execute import python_execute_node
from app.graph.nodes.python_generator import python_generator_node
from app.graph.nodes.report_generator import report_generator_node
from app.graph.nodes.scheme_recall import scheme_recall_node
from app.graph.nodes.sql_execute import sql_execute_node
from app.graph.nodes.sql_generator import sql_generator_node
from app.graph.nodes.supervisor import supervisor_node
from app.graph.nodes.table_relation import table_relation_node

__all__ = [
    "evidence_recall_node",
    "scheme_recall_node",
    "table_relation_node",
    "feasibility_node",
    "planner_node",
    "human_feedback_node",
    "supervisor_node",
    "sql_generator_node",
    "sql_execute_node",
    "python_generator_node",
    "python_execute_node",
    "python_analyze_node",
    "report_generator_node",
]
