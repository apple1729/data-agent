"""主管调度节点。

**整个架构的核心。** 每一轮让大模型看"用户问题 + 已发生的执行轨迹"，
动态决定下一步派给哪个子 Agent：

    SQL_GENERATION      去取数
    PYTHON_GENERATION   对已有结果做分析/绘图（必须已有 SQL 结果）
    REPORT_GENERATION   写最终报告（任务的最后一步）
    END                 结束（做完了 / 没法继续 / 出错）

【它和别的节点不一样的地方】
  别的节点是"读状态 → 干活 → 写状态"，它是**改变计划的结构**：
    1. 每轮往 plan.execution_plan **末尾追加一步**
    2. 把 CURRENT_STEP 指向刚追加的那一步
    3. 下游子 Agent 通过 Plan.get_step(CURRENT_STEP) 按位置读到它
  这就是"动态派单"——下游节点完全不知道计划是运行时生成的。

【首次进入要清空草稿计划】
  Planner 产出的那 2~3 步是**给用户看的草稿**，不是执行指令。
  所以第一次进 Supervisor（iteration==0）要把步骤全清掉，
  只留 thought_process 给最终报告引用，然后从零开始动态派单。

【熔断】最多 12 轮，防止大模型死循环。

【出错兜底】决策失败时不抛异常（会让整张图返回 500），而是走 END，
  让前端收到一个明确结束的任务。

对应 Java 的 SupervisorNode + SupervisorEdge。
"""

import asyncio
import json
import logging

from app.graph.node_names import GraphNode
from app.graph.state import AgentState, StateKey
from app.llm import client, structured
from app.llm.dto import Plan, SupervisorDecision, ToolParameters

logger = logging.getLogger(__name__)

# 最大决策轮数（照抄 Java）
MAX_ITERATIONS = 12

# 表示"结束"。这个值要和 builder.py 里 path_map 的键对得上。
END = "__END__"

# 各阶段失败时会写进 EXECUTION_OUTPUT 的 key 后缀
_ERROR_SUFFIXES = (
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


async def supervisor_node(state: AgentState) -> dict:
    user_question = state.get(StateKey.REWRITE_QUERY, "")
    iteration = state.get(StateKey.SUPERVISOR_ITERATION, 0)

    # ---- 1) 取计划（解析失败就新建一个空的）----
    try:
        plan = Plan.model_validate_json(state.get(StateKey.PLAN, "{}"))
    except Exception:  # noqa: BLE001
        logger.warning("计划解析失败，从空计划开始")
        plan = Plan()

    # ---- 2) 首次进入：清空 Planner 留下的草稿步骤 ----
    if iteration == 0 and plan.execution_plan:
        print(
            f"  [SUPERVISOR] 首次进入，清空草稿计划的 "
            f"{len(plan.execution_plan)} 个步骤"
        )
        plan.execution_plan.clear()

    history = plan.execution_plan

    # ---- 3) 熔断 ----
    if iteration >= MAX_ITERATIONS:
        print(f"  [SUPERVISOR] 已达最大轮次 {MAX_ITERATIONS}，强制结束")
        return {
            StateKey.NEXT_NODE: END,
            StateKey.SUPERVISOR_ITERATION: iteration + 1,
        }

    # ---- 4) 让大模型决策 ----
    trace = _build_agent_trace(state, history)
    decision = await asyncio.to_thread(_decide_next_step, user_question, trace)
    print(
        f"  [SUPERVISOR] 第 {iteration + 1} 轮决策 → "
        f"next={decision.next_agent or '?'} finished={decision.finished}"
    )
    if decision.thought:
        print(f"      理由：{decision.thought[:80]}")

    # ---- 5) 决策结束 ----
    if decision.finished or (decision.next_agent or "").strip().upper() == "END":
        return {
            StateKey.NEXT_NODE: END,
            StateKey.SUPERVISOR_ITERATION: iteration + 1,
        }

    # ---- 6) 把决策追加成新的一步，供下游子 Agent 读取 ----
    next_node = _normalize_node_name(decision.next_agent)
    if next_node == END:
        logger.warning("无法识别的 next_agent=%r，当作结束处理", decision.next_agent)
        return {
            StateKey.NEXT_NODE: END,
            StateKey.SUPERVISOR_ITERATION: iteration + 1,
        }

    plan.append_step(
        next_node,
        ToolParameters(
            instruction=decision.task_instruction or "",
            summary_and_recommendations=decision.summary_and_recommendations or "",
        ),
    )
    new_current_step = len(plan.execution_plan)

    print(f"      派单 → {next_node}（第 {new_current_step} 步）")

    return {
        StateKey.PLAN: plan.model_dump_json(),
        StateKey.CURRENT_STEP: new_current_step,
        StateKey.NEXT_NODE: next_node,
        StateKey.SUPERVISOR_ITERATION: iteration + 1,
    }


# ---------------------------------------------------------------------------
# 执行轨迹：把"已经发生了什么"整理成文字给大模型看
# ---------------------------------------------------------------------------


def _build_agent_trace(state: AgentState, history) -> str:
    if not history:
        return "（暂无历史，这是第一轮决策）"

    output = state.get(StateKey.EXECUTION_OUTPUT, {}) or {}
    lines: list[str] = []

    for index, step in enumerate(history):
        step_no = index + 1
        line = f"第{step_no}步 -> 工具[{step.tool_to_use}]"
        instruction = step.tool_parameters.instruction
        if instruction:
            line += f" | 指令: {instruction}"
        line += _format_errors(output, step_no)
        lines.append(line + "\n")

    # 最后一步是否失败——失败了就不展示"最近产出"，
    # 免得把上一轮遗留的旧结果当成本轮的成果，误导大模型
    last_step_no = len(history)
    last_step = history[-1]
    last_failed = any(
        f"step_{last_step_no}{suffix}" in output for suffix in _ERROR_SUFFIXES
    )
    show_sql = not (last_failed and last_step.tool_to_use == GraphNode.SQL_GENERATION)
    show_python = not (
        last_failed and last_step.tool_to_use == GraphNode.PYTHON_GENERATION
    )

    if show_sql:
        sql = state.get(StateKey.SQL_GENERATION_RESULT) or ""
        if sql.strip():
            lines.append(f"[最近 SQL 生成]: {_truncate(sql, 500)}\n")
        sql_result = state.get(StateKey.SQL_EXECUTION_RESULT)
        if sql_result is not None:
            lines.append(
                f"[最近 SQL 执行结果]: {_truncate(_to_text(sql_result), 800)}\n"
            )

    if show_python:
        code = state.get(StateKey.PYTHON_GENERATION_RESULT) or ""
        if code.strip():
            lines.append(f"[最近 Python 代码]: {_truncate(code, 400)}\n")
        py_result = state.get(StateKey.PYTHON_EXECUTION_RESULT)
        if py_result is not None:
            lines.append(
                f"[最近 Python 执行结果]: {_truncate(_to_text(py_result), 800)}\n"
            )

    return "".join(lines)


def _format_errors(output: dict, step_no: int) -> str:
    """把某一步的各种失败标记拼成一句提示。

    优先展示"阶段化错误"（是生成失败了、还是执行失败了），
    最后才回退到通用的 step_N_error——因为通用那个容易被后续节点覆盖，
    大模型就看不到真正的根因了。
    """
    stage_errors = (
        ("_sqlgen_error", "❌ SQL 生成失败", 500),
        ("_sqlexec_error", "❌ SQL 执行失败", 500),
        ("_sqlexec_skipped", "⏭ SQL 执行跳过", 200),
        ("_pygen_error", "❌ Python 生成失败", 500),
        ("_pyexec_error", "❌ Python 执行失败", 600),
        ("_pyexec_skipped", "⏭ Python 执行跳过", 200),
        ("_pyanalyze_error", "❌ Python 分析失败", 500),
        ("_pyanalyze_skipped", "⏭ Python 分析跳过", 200),
    )
    text = ""
    found_stage_error = False
    for suffix, label, limit in stage_errors:
        value = output.get(f"step_{step_no}{suffix}")
        if value:
            text += f" | {label}: {_truncate(str(value), limit)}"
            found_stage_error = True

    if not found_stage_error:
        generic = output.get(f"step_{step_no}_error")
        if generic:
            text += f" | ❌ 失败: {_truncate(str(generic), 600)}"
    return text


# ---------------------------------------------------------------------------
# 调大模型决策
# ---------------------------------------------------------------------------

# 这段提示词是**硬编码在 Java 代码里的**，不是从模板文件读的，照搬过来。
_DECISION_PROMPT = """你是一个数据分析任务的 Supervisor（主管 Agent），负责调度多个 Sub-Agent 完成用户问题。

# 用户原始问题
{question}

# 已经发生的执行轨迹
{trace}

# 你可派遣的 Sub-Agent
- SQL_GENERATION : 负责根据自然语言指令生成并执行 SQL，从数据库取数。
- PYTHON_GENERATION : 负责对已有 SQL 结果集做进一步的数据分析/计算/绘图。必须在已有 SQL 结果之后才能调用。
- REPORT_GENERATION : 把全部已收集的数据生成最终面向用户的报告。整个任务的最后一步必须是它。
- END : 任务终止（异常/无法继续/已经生成报告）。

# 决策原则
1. 第一步通常是 SQL_GENERATION（先取数）。
2. 仅在已有可用 SQL 结果时才派 PYTHON_GENERATION。
3. 当数据已收集足够能回答用户问题时，派 REPORT_GENERATION 收尾，然后下一轮直接 finished=true。
4. 不要无意义重复同一类操作。

# 失败处理原则（重要）
- 如果上一步在轨迹中标记了"❌ 失败"，请仔细阅读失败原因：
  · SQL 失败（语法/字段不存在等）：可以再次派 SQL_GENERATION，并在 instruction 中**明确指出**上次的错误以及如何修正。
  · Python 失败（代码错误/执行异常）：可以再次派 PYTHON_GENERATION 让它修正。
  · 同一类失败**累计达到 2 次**就不要再重试，应该改派 REPORT_GENERATION 把已有数据汇总告知用户，或在彻底无数据时 finished=true 结束。
- 注意区分"失败"和"成功但结果为空"：结果为空也可能是正常业务结果，不应反复重试。

# 输出格式
{format}
"""


def _decide_next_step(user_question: str, trace: str) -> SupervisorDecision:
    prompt = _DECISION_PROMPT.format(
        question=user_question,
        trace=trace,
        format=structured.format_hint(SupervisorDecision),
    )
    try:
        raw = client.chat(prompt)
        return structured.parse(raw, SupervisorDecision)
    except Exception as exc:  # noqa: BLE001
        # 决策失败不往上抛——抛了整张图会崩、用户拿到 500。
        # 这里走"安全终止"，让用户收到一个明确结束的任务。
        logger.error("Supervisor 决策失败，安全终止: %s", exc)
        return SupervisorDecision(
            thought=f"Supervisor 决策异常: {exc}",
            next_agent="END",
            finished=True,
        )


def _normalize_node_name(agent: str | None) -> str:
    """把大模型写的各种叫法归一到图节点名。"""
    upper = (agent or "").strip().upper()
    if upper in ("SQL", "SQL_GENERATION", "SQL_GENERATE_NODE"):
        return GraphNode.SQL_GENERATION
    if upper in ("PYTHON", "PYTHON_GENERATION", "PYTHON_GENERATE_NODE"):
        return GraphNode.PYTHON_GENERATION
    if upper in ("REPORT", "REPORT_GENERATION", "REPORT_GENERATOR_NODE"):
        return GraphNode.REPORT_GENERATION
    return END


def _to_text(value) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _truncate(text: str, limit: int) -> str:
    if text is None:
        return ""
    return text if len(text) <= limit else text[:limit] + "...(truncated)"
