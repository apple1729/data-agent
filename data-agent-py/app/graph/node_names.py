"""图节点名常量。

这些字符串是**和前端的硬契约**：前端拿 artifact.name 去自己的
NODE_COMPONENTS 表里查渲染组件（见前端 WorkspacePage.vue）。
改名必须前后端一起改，否则卡片会渲染不出来。

对应 Java 版的 DataAgentSpec.Graph.Node。
"""


class GraphNode:
    """13 个节点的名字，一字不差地对齐前端写死的映射表。

    右边是每个节点的一句话说明。整条流水线分三段（下面用分隔线标出）：
      第一段摸家底 → 第二段想方案并交人拍板 → 第三段由主管派活干活。
    """

    # -------------------- 第一段：摸家底 --------------------
    EVIDENCE_RECALL = "EVIDENCE_RECALL_NODE"                # 证据召回：翻知识库，找能帮忙的业务术语和历史问答
    SCHEMA_RECALL = "SCHEME_RECALL_NODE"                    # 表结构召回：从几百张表里把沾边的捞出来（值是 SCHEME，少个 A，别改）
    TABLE_RELATION = "TABLE_RELATION_NODE"                  # 表关系推理：挑出真正要用的表，补全外键关联（最复杂）

    # -------------------- 第二段：想方案 + 人工拍板 --------------------
    FEASIBILITY_ASSESSMENT = "FEASIBILITY_ASSESSMENT_NODE"  # 可行性评估：判断这问题能不能用数据分析回答
    PLANNER = "PLANNER_NODE"                                # 任务规划：拆解成一步步的执行计划
    HUMAN_FEEDBACK = "HUMAN_FEEDBACK_NODE"                  # 人工审核：计划拿给人看，等同意/不同意（图中断点）

    # -------------------- 第三段：主管派活，多 Agent 干活 --------------------
    SUPERVISOR = "SUPERVISOR_NODE"                          # 主管调度：决定下一步派谁干活（会转圈，有轮次上限）
    SQL_GENERATION = "SQL_GENERATE_NODE"                    # 生成 SQL：写查询语句
    SQL_EXECUTION = "SQL_EXECUTE_NODE"                      # 执行 SQL：真去数据库里跑，拿结果
    PYTHON_GENERATION = "PYTHON_GENERATE_NODE"              # 生成分析代码：需要统计/画图时写 Python
    PYTHON_EXECUTION = "PYTHON_EXECUTE_NODE"                # 执行分析代码：丢进 Docker 沙箱跑
    PYTHON_ANALYSIS = "PYTHON_ANALYZE_NODE"                 # 解读分析结果：把跑出来的数字翻译成人话
    REPORT_GENERATION = "REPORT_GENERATOR_NODE"             # 生成报告：汇总成一份完整分析报告（终点）

    # 人工审核节点就是中断节点
    INTERRUPT_NODE = HUMAN_FEEDBACK


# 节点执行顺序（图跑起来的真实顺序，前端也按这个排流水线）
NODE_ORDER = [
    GraphNode.EVIDENCE_RECALL,
    GraphNode.SCHEMA_RECALL,
    GraphNode.TABLE_RELATION,
    GraphNode.FEASIBILITY_ASSESSMENT,
    GraphNode.PLANNER,
    GraphNode.HUMAN_FEEDBACK,
    GraphNode.SUPERVISOR,
    GraphNode.SQL_GENERATION,
    GraphNode.SQL_EXECUTION,
    GraphNode.PYTHON_GENERATION,
    GraphNode.PYTHON_EXECUTION,
    GraphNode.PYTHON_ANALYSIS,
    GraphNode.REPORT_GENERATION,
]

# 全部节点跑完后，前端靠这个约定判断「整条图结束了」
END_ARTIFACT_NAME = "__END__"
