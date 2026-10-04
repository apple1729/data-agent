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


class ExecutionStep(BaseModel):
    """执行计划里的一步。对应 Java 的 Plan.ExecutionStep。"""

    step: int = Field(default=0, description="步骤顺序号")
    tool_to_use: str = Field(default="", description="这一步交给哪个节点做")
    instruction: str = Field(default="", description="这一步的具体要求")
    sql_query: str = Field(default="", description="SQL 生成节点跑完后回填这里")
    summary_and_recommendations: str = Field(
        default="", description="报告节点专用，报告大纲"
    )


class Plan(BaseModel):
    """执行计划。对应 Java 的 Plan。"""

    thought_process: str = Field(
        default="", description="简要分析思路，要提到检查了哪些表和字段"
    )
    execution_plan: list[ExecutionStep] = Field(
        default_factory=list, description="执行计划的步骤列表"
    )
