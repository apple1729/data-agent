"""大模型输出的结构化格式定义。

对应 Java 版的 entity/dto/ 下那些类（EvidenceQueryRewriteDTO、Plan 等）。

【为什么用 pydantic】
  它能一键生成 JSON Schema（喂给模型当格式说明），
  还能自动校验模型返回的数据。Java 里靠 BeanOutputConverter 干这两件事。

【字段名必须和 Java 的 @JsonProperty 一致】
  因为 prompt 模板里的示例就是按那些字段名写的，
  改了就和分析不上了。
"""

from pydantic import BaseModel, Field


class EvidenceQueryRewrite(BaseModel):
    """查询重写的结果。对应 Java 的 EvidenceQueryRewriteDTO。"""

    standalone_query: str = Field(default="", description="重写后的完整句子")


class ToolParameters(BaseModel):
    """工具参数。对应 Java 的 Plan.ToolParameters。

    注意：这几个字段在 ExecutionStep 里**也有一份（顶层）**，
    是原项目的冗余设计，照抄不改。
    """

    instruction: str = Field(
        default="",
        description="当工具是 SQL_GENERATE_NODE 时填详细的 SQL 需求；"
        "是 PYTHON_GENERATE_NODE 时填详细的编程需求",
    )
    summary_and_recommendations: str = Field(
        default="", description="REPORT_GENERATOR_NODE 专用，报告大纲"
    )
    sql_query: str = Field(
        default="", description="SQL 生成节点跑完后回填这里"
    )


class ExecutionStep(BaseModel):
    """执行计划里的一步。对应 Java 的 Plan.ExecutionStep。"""

    step: int = Field(default=0, description="步骤顺序号")
    tool_to_use: str = Field(
        default="",
        description="这一步交给哪个节点做，取值形如 SQL_GENERATE_NODE / "
        "PYTHON_GENERATE_NODE / REPORT_GENERATOR_NODE",
    )
    tool_parameters: ToolParameters = Field(
        default_factory=ToolParameters, description="工具参数"
    )
    instruction: str = Field(
        default="",
        description="当工具是 SQL_GENERATE_NODE 时填详细的 SQL 需求；"
        "是 PYTHON_GENERATE_NODE 时填详细的编程需求",
    )
    summary_and_recommendations: str = Field(
        default="", description="REPORT_GENERATOR_NODE 专用，报告大纲"
    )
    sql_query: str = Field(
        default="", description="SQL 生成节点跑完后回填这里"
    )


class Plan(BaseModel):
    """执行计划。对应 Java 的 Plan。"""

    thought_process: str = Field(
        default="", description="简要分析思路，要提到检查了哪些表和字段"
    )
    execution_plan: list[ExecutionStep] = Field(
        default_factory=list, description="执行计划的步骤列表"
    )

    def get_step(self, number: int) -> ExecutionStep:
        """取第 N 步。

        ★ 注意是按**位置**取的（execution_plan[number - 1]），
          不是按每个步骤的 step 字段的值去找。
          这是 Java 的行为，也是 Supervisor"动态追加步骤"机制的基础：
          Supervisor 每轮往列表末尾追加一个新步骤，同时把 CURRENT_STEP +1，
          下游节点就能靠位置取到"最新追加的那一步"。
        """
        index = number - 1
        if index < 0 or index >= len(self.execution_plan):
            raise IndexError(
                f"计划里没有第 {number} 步（当前共 {len(self.execution_plan)} 步）"
            )
        return self.execution_plan[index]

    def append_step(self, tool_name: str, params: ToolParameters) -> None:
        """往计划末尾追加一步。Supervisor 每轮派单时调用。"""
        self.execution_plan.append(
            ExecutionStep(
                step=len(self.execution_plan) + 1,
                tool_to_use=tool_name,
                tool_parameters=params,
            )
        )


class SupervisorDecision(BaseModel):
    """Supervisor 单轮决策的输出。对应 Java 的 SupervisorNode.SupervisorDecision。"""

    thought: str = Field(default="", description="简要描述你为什么这样决策")
    next_agent: str = Field(
        default="",
        description="下一个要派遣的 Sub-Agent，可选："
        "SQL_GENERATION / PYTHON_GENERATION / REPORT_GENERATION / END",
    )
    task_instruction: str = Field(
        default="", description="派给该 Sub-Agent 的任务指令（SQL/Python 节点会读这个）"
    )
    summary_and_recommendations: str = Field(
        default="",
        description="仅当 next_agent=REPORT_GENERATION 时填写，作为报告大纲",
    )
    finished: bool = Field(
        default=False, description="整个任务是否已完成；填 true 时流程走向结束"
    )
