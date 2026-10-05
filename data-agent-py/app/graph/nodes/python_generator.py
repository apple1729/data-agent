"""Python 代码生成节点。

根据"当前计划步骤的指令" + "表结构" + "上游 SQL 的结果样例"，
让大模型写一段 Python 分析代码。

【代码的运行约定】（prompt 里会告诉模型）
  输入：从 sys.stdin 读 JSON（就是 SQL 的结果行）
  输出：把结果 print 成 JSON，走 stdout
  出错：traceback 打到 stderr，退出码非 0

【前置条件】必须先有 SQL 执行结果——没有数据就没法分析。

对应 Java 的 PythonGeneratorNode。
"""

import asyncio
import json
import logging

from app import settings
from app.domain.schema import Schema
from app.graph.state import AgentState, StateKey
from app.llm import client, markdown, prompts
from app.llm.dto import Plan

logger = logging.getLogger(__name__)


async def python_generator_node(state: AgentState) -> dict:
    current_step = state.get(StateKey.CURRENT_STEP, 1)

    try:
        schema = Schema.model_validate_json(state.get(StateKey.TABLE_RELATION, "{}"))

        sql_result = state.get(StateKey.SQL_EXECUTION_RESULT)
        if not sql_result:
            raise ValueError("缺少前置的 SQL 执行结果，没法做 Python 分析")

        # 把 SQL 结果的前若干行作为"样例输入"喂给模型，
        # 让它知道数据长什么样（列名、值的形态），才能写出对的代码
        rows = (sql_result.get("resultSet") or {}).get("data") or []
        sample_input = json.dumps(rows, ensure_ascii=False)

        plan = Plan.model_validate_json(state.get(StateKey.PLAN, "{}"))
        plan_step = plan.get_step(current_step)
        plan_description = json.dumps(
            plan_step.tool_parameters.model_dump(), ensure_ascii=False
        )

        prompt = prompts.render(
            "python-generator",
            {
                # prompt 里写的是"最大内存：{python_memory} MB"，所以传纯数字
                "python_memory": settings.PYTHON_SANDBOX_MEMORY.rstrip("mM"),
                "python_timeout": str(settings.PYTHON_SANDBOX_TIMEOUT),
                "database_schema": schema.build_scheme_prompt(),
                "sample_input": sample_input,
                "plan_description": plan_description,
            },
        )

        # 和 SQL 生成一样，是当 system 消息发的
        raw = await asyncio.to_thread(client.chat, None, prompt)

        # 调试用：模型偶尔会不听话，返回一段自然语言描述而不是代码，
        # 那样沙箱执行时会在第 1 行报 SyntaxError（而且报错信息看着莫名其妙）。
        # 把开头打出来，一眼就能看出是"没输出代码"还是"代码本身有问题"。
        print(f"      模型返回开头: {raw[:120]!r}")

        code = markdown.extract_raw_text(raw).strip()
        if not code:
            raise ValueError("生成的 Python 代码为空")

        print(f"  [PYTHON_GENERATE] 第 {current_step} 步：生成代码 {len(code)} 字符")
        print(f"      代码第一行: {code.splitlines()[0][:100] if code.splitlines() else ''}")

        return {StateKey.PYTHON_GENERATION_RESULT: code}

    except Exception as exc:  # noqa: BLE001
        logger.exception("[PYTHON_GENERATE] 失败 step=%s", current_step)
        summary = f"PYTHON_GENERATION 失败: {type(exc).__name__} - {exc}"
        print(f"  [PYTHON_GENERATE] 失败（不中断流程）：{summary}")

        # 清空旧值（免得下游误用上一轮的代码），
        # 只写阶段化的 _pygen_error，不写通用的 _error——
        # 否则会把后面节点写的根因覆盖掉
        return {
            StateKey.PYTHON_GENERATION_RESULT: "",
            StateKey.EXECUTION_OUTPUT: {f"step_{current_step}_pygen_error": summary},
        }
