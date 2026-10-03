"""图的状态定义（13 个节点共享的"便签本"）。

对应 Java 版的 DataAgentSpec.Graph.StateKey + GraphConfiguration 里的
KeyStrategyFactory。

【这个文件解决什么问题】
  13 个节点之间不直接通信，全靠这个字典传递数据：
      节点A 往字典里写 → 节点B 从字典里读
  所以字段名必须和 Java 版、前端三方完全一致，错一个字母就对不上。

【为什么要区分"覆盖"和"累加"】
  绝大多数字段是"覆盖"——新结果把旧结果顶掉，这是 LangGraph 的默认行为。
  但 EXECUTION_OUTPUT 必须"累加"——Supervisor 会循环多轮，
  每一轮的结果都得留着，否则写报告时会丢内容。详见 merge_dict 的注释。
"""

from typing import Annotated, Any, TypedDict


class StateKey:
    """状态字段名常量。

    取值全部照抄 Java 的 DataAgentSpec.Graph.StateKey，一个字符都不能改。
    """

    # ---------- 入参：图启动时由执行器写入 ----------
    USER_INPUT = "input"                    # 用户原始问题（来自 A2A Message 的文本）
    DATABASE_ID = "databaseId"              # 查哪个库（来自 Message.metadata）
    MULTI_TURN_CONTEXT = "MULTI_TURN_CONTEXT"   # 多轮对话历史（原项目留了钩子没实现）

    # ---------- 召回阶段 ----------
    REWRITE_QUERY = "REWRITE_QUERY"         # 改写后的检索 query
    EVIDENCE = "EVIDENCE"                   # 业务术语 + 历史问答拼成的证据文本
    TABLE_SCHEME = "TABLE_SCHEME"           # 表级召回结果（注意是 SCHEME 不是 SCHEMA）
    COLUMN_SCHEME = "COLUMN_SCHEME"         # 列级召回结果
    TABLE_RELATION = "TABLE_RELATION_OUTPUT"    # 表关系推理后的最终 schema（JSON 字符串）

    # ---------- 规划阶段 ----------
    PLAN = "PLANNER_NODE_OUTPUT"            # Planner 产出的执行计划
    VALIDATION_ERROR = "PLAN_VALIDATION_ERROR"
    VALIDATION_STATUS = "PLAN_VALIDATION_STATUS"
    REPAIR_COUNT = "PLAN_REPAIR_COUNT"      # 计划被拒绝的次数（>=3 熔断）
    NEXT_NODE = "PLAN_NEXT_NODE"            # Supervisor 决定下一步去哪
    CURRENT_STEP = "PLAN_CURRENT_STEP"      # 当前执行到第几步
    SUPERVISOR_ITERATION = "SUPERVISOR_ITERATION"    # Supervisor 已经派了几轮
    EXECUTION_OUTPUT = "PLAN_EXECUTE_NODE_OUTPUT"    # ★ 各子 Agent 的结果（累加，不覆盖）

    # ---------- 人工审核阶段 ----------
    CONFIRMATION_APPROVED = "confirmationApproved"   # 用户是否批准（Boolean）
    CONFIRMATION_FEEDBACK = "confirmationFeedback"   # 拒绝时的反馈文本
    HUMAN_NEXT_NODE = "HUMAN_NEXT_NODE"              # 审核后去哪（SUPERVISOR/PLANNER/END）

    # ---------- 执行阶段 ----------
    FEASIBILITY_RESULT = "FEASIBILITY_ASSESSMENT_NODE_OUTPUT"
    SQL_GENERATION_RESULT = "SQL_GENERATE_OUTPUT"
    SQL_EXECUTION_RESULT = "SQL_EXECUTE_OUTPUT"
    PYTHON_GENERATION_RESULT = "PYTHON_GENERATE_NODE_OUTPUT"
    PYTHON_EXECUTION_RESULT = "PYTHON_EXECUTE_NODE_OUTPUT"
    REPORT_RESULT = "REPORT_GENERATOR_NODE_OUTPUT"


def merge_dict(old: dict | None, new: dict | None) -> dict:
    """字典合并函数，给 EXECUTION_OUTPUT 用。

    【为什么需要它】
      LangGraph 默认是"覆盖"：节点返回什么，就把这个字段整个替换掉。
      但 Supervisor 会循环多轮，每轮都往 EXECUTION_OUTPUT 里塞结果：

        第 1 轮：{"step_1": "每个县的学校数..."}
        第 2 轮：{"step_2": "相关性 0.73..."}      ← 默认行为下 step_1 就没了
        写报告时只看到 step_2，报告内容缺一半

      挂上这个函数后变成"累加"：
        第 2 轮：{"step_1": "...", "step_2": "..."}   ← 两份都在

    【为什么这个 bug 难查】
      不报错、日志没警告、前端卡片照样正常显示（卡片是靠 artifact 发的，
      不经过 state），只有仔细读最终报告才会发现少了内容。

    LangGraph 的约定：reducer 接收 (旧值, 新值)，返回合并后的值。
    """
    return {**(old or {}), **(new or {})}


class AgentState(TypedDict, total=False):
    """图的完整状态。

    total=False 表示所有字段都是可选的——状态是逐步长出来的，
    图刚启动时只有 input 和 databaseId，后面的字段由各节点填。
    """

    # ---------- 入参 ----------
    input: str
    databaseId: str
    MULTI_TURN_CONTEXT: str

    # ---------- 召回 ----------
    REWRITE_QUERY: str
    EVIDENCE: str
    TABLE_SCHEME: list[Any]
    COLUMN_SCHEME: list[Any]
    TABLE_RELATION_OUTPUT: str

    # ---------- 规划 ----------
    PLANNER_NODE_OUTPUT: str
    PLAN_VALIDATION_ERROR: str
    PLAN_VALIDATION_STATUS: str
    PLAN_REPAIR_COUNT: int
    PLAN_NEXT_NODE: str
    PLAN_CURRENT_STEP: int
    SUPERVISOR_ITERATION: int
    # ★ 唯一一个用 Annotated 挂 reducer 的字段——累加，不覆盖
    PLAN_EXECUTE_NODE_OUTPUT: Annotated[dict[str, Any], merge_dict]

    # ---------- 人工审核 ----------
    confirmationApproved: bool
    confirmationFeedback: str
    HUMAN_NEXT_NODE: str

    # ---------- 执行 ----------
    FEASIBILITY_ASSESSMENT_NODE_OUTPUT: str
    SQL_GENERATE_OUTPUT: str
    SQL_EXECUTE_OUTPUT: Any
    PYTHON_GENERATE_NODE_OUTPUT: str
    PYTHON_EXECUTE_NODE_OUTPUT: Any
    REPORT_GENERATOR_NODE_OUTPUT: str
