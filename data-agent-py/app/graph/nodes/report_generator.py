"""报告生成节点。

把前面所有步骤的结果汇总，生成一份面向用户的 Markdown 报告。**流水线终点。**

【两个要点】
  1. 数据来源是累加的 EXECUTION_OUTPUT——正因为它是"累加"而不是"覆盖"，
     这里才能看到所有轮次的结果（这就是那个 merge reducer 存在的意义）
  2. 要**过滤掉系统态 key**：`_error` / `_sqlgen_error` / `_analysis` 这些
     是给 Supervisor 做决策用的，塞进报告里只会干扰用户

【和 Java 的一处差异】
  Java 版是流式输出（返回 Flux，前端能看到打字机效果）。
  Python 这边先做成非流式——一次性生成完整报告再存进状态。
  前端仍然正常显示，只是报告内容一次性出现，不是逐字蹦。
  要打字机效果的话后面可以用 LangGraph 的自定义流，属于锦上添花。

对应 Java 的 ReportGeneratorNode。
"""

import asyncio

from app.graph.state import AgentState, StateKey
from app.llm import client, prompts
from app.llm.dto import Plan

# 给大模型看的 ECharts 图表配置示例（照抄 Java 里的常量）
CLEAN_JSON_EXAMPLE = """{
    "title": { "text": "月度销售额" },
    "tooltip": { "trigger": "axis" },
    "xAxis": { "type": "category", "data": ["1月", "2月"] },
    "yAxis": { "type": "value" },
    "series": [
        { "type": "bar", "data": [120, 200] }
    ]
}"""

# 这些后缀的 key 是"系统态"，不进用户报告（照抄 Java 的过滤清单）
SYSTEM_KEY_SUFFIXES = (
    "_analysis",
    "_error",
    "_sqlgen_error",
    "_sqlexec_error",
    "_sqlexec_skipped",
    "_pygen_error",
    "_pyexec_error",
    "_pyexec_skipped",
    "_pyanalyze_error",
    "_pyanalyze_skipped",
)


async def report_generator_node(state: AgentState) -> dict:
    rewrite_query = state.get(StateKey.REWRITE_QUERY, "")
    plan = Plan.model_validate_json(state.get(StateKey.PLAN, "{}"))
    execution_results = state.get(StateKey.EXECUTION_OUTPUT, {}) or {}
    current_step = state.get(StateKey.CURRENT_STEP, 1)

    # 报告的写作要求由 Supervisor 派单时给出（在 tool_parameters 里）
    try:
        summary = plan.get_step(current_step).tool_parameters.summary_and_recommendations or ""
    except IndexError:
        summary = ""

    prompt = prompts.render(
        "report-generator-plain",
        {
            "user_requirements_and_plan": _build_user_requirements_and_plan(
                rewrite_query, plan
            ),
            "analysis_steps_and_data": _build_analysis_steps_and_data(
                plan, execution_results
            ),
            "summary_and_recommendations": summary,
            "json_example": CLEAN_JSON_EXAMPLE,
            "optimization_section": "",
        },
    )

    report = (await asyncio.to_thread(client.chat, prompt)).strip()
    if not report:
        raise ValueError("生成的报告为空")

    print(f"  [REPORT_GENERATOR] 汇总 {len(execution_results)} 份结果，报告 {len(report)} 字符")

    return {StateKey.REPORT_RESULT: report}


def _build_user_requirements_and_plan(user_input: str, plan: Plan) -> str:
    """拼"用户要什么 + 计划怎么做"这一段。"""
    parts = [
        "## 用户原始需求\n",
        f"{user_input}\n\n",
        "## 执行计划概述\n",
        f"**思考过程**: {plan.thought_process}\n\n",
        "## 详细执行步骤\n",
    ]
    for index, step in enumerate(plan.execution_plan):
        parts.append(f"### 步骤 {index + 1}: 步骤编号 {step.step}\n")
        parts.append(f"**工具**: {step.tool_to_use}\n")
        parts.append(f"**参数描述**: {step.tool_parameters.instruction}\n")
        parts.append("\n")
    return "".join(parts)


def _build_analysis_steps_and_data(plan: Plan, execution_results: dict) -> str:
    """拼"每步干了什么 + 拿到了什么数据"这一段。"""
    parts = ["## 数据执行结果\n"]

    if not execution_results:
        parts.append("暂无执行结果数据\n")
        return "".join(parts)

    for step_key, step_result in execution_results.items():
        # 系统态的 key 跳过（错误信息、跳过标记等）
        if step_key.endswith(SYSTEM_KEY_SUFFIXES):
            continue
        parts.append(f"### {step_key}\n")

        # step_3 → 去查计划里的第 3 步，补上它的描述和 SQL
        try:
            index = int(step_key.replace("step_", "")) - 1
        except ValueError:
            index = -1
        if 0 <= index < len(plan.execution_plan):
            step = plan.execution_plan[index]
            params = step.tool_parameters
            parts.append(f"**步骤编号**: {step.step}\n")
            parts.append(f"**使用工具**: {step.tool_to_use}\n")
            parts.append(f"**参数描述**: {params.instruction}\n")
            if params.sql_query:
                parts.append(f"**执行SQL**: \n```sql\n{params.sql_query}\n```\n")

        parts.append(f"**执行结果**: \n```json\n{step_result}\n```\n\n")

        # 如果有对应的 Python 分析结果，补充展示
        analysis = execution_results.get(f"{step_key}_analysis")
        if analysis:
            parts.append(f"**Python 分析结果**: {analysis} ")

    return "".join(parts)
