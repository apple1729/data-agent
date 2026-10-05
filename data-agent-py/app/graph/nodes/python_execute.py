"""Python 代码执行节点。

把上一步生成的代码**丢进 Docker 沙箱**执行。

【安全边界不可省】
  代码是大模型现写的，一个跑野了的分支就能删文件、偷环境变量、往外发数据。
  沙箱参数（--network none / --cpus 1 / --memory 512m /
  --pids-limit 128 / no-new-privileges）一条都不能去掉。

【注意 SimplePythonExecutor 的契约】
  它**不抛异常**，失败信息放在 success=False 的结果里。
  所以这里要主动把 success=False 转成错误标记上报给 Supervisor，
  否则下游 Analyze 会以为"执行成功了"而去分析一段报错文本。

对应 Java 的 PythonExecuteNode + SimplePythonExecutor。
"""

import asyncio
import json
import logging

from app.graph.state import AgentState, StateKey
from app.sandbox import python_executor

logger = logging.getLogger(__name__)


async def python_execute_node(state: AgentState) -> dict:
    current_step = state.get(StateKey.CURRENT_STEP, 1)
    code = (state.get(StateKey.PYTHON_GENERATION_RESULT) or "").strip()

    # 上游没生成代码 → 跳过，不写通用 _error（免得覆盖 _pygen_error 的根因）
    if not code:
        print(f"  [PYTHON_EXECUTE] 第 {current_step} 步：上游代码为空，跳过")
        return {
            StateKey.EXECUTION_OUTPUT: {
                f"step_{current_step}_pyexec_skipped": (
                    "PYTHON_EXECUTION 跳过：上游未生成有效 Python 代码"
                )
            }
        }

    try:
        sql_result = state.get(StateKey.SQL_EXECUTION_RESULT)
        if not sql_result:
            raise ValueError("缺少前置的 SQL 执行结果，没法给分析代码喂数据")

        rows = (sql_result.get("resultSet") or {}).get("data") or []
        input_json = json.dumps(rows, ensure_ascii=False)
        if not input_json.strip():
            raise ValueError("SQL 结果为空，没法给分析代码喂数据")

        output = await asyncio.to_thread(python_executor.execute, code, input_json)

        # 执行没成功 → 主动上报错误（沙箱不会抛异常，得我们自己判断）
        if not output.success:
            summary = f"PYTHON_EXECUTION 运行失败: {output.output or output.error}"[:600]
            print(f"  [PYTHON_EXECUTE] 第 {current_step} 步执行失败")
            return {
                StateKey.PYTHON_EXECUTION_RESULT: output.model_dump(),
                StateKey.EXECUTION_OUTPUT: {
                    f"step_{current_step}_pyexec_error": summary
                },
            }

        print(f"  [PYTHON_EXECUTE] 第 {current_step} 步执行成功")
        for line in (output.output or "").splitlines()[:3]:
            print(f"      {line[:120]}")

        return {StateKey.PYTHON_EXECUTION_RESULT: output.model_dump()}

    except Exception as exc:  # noqa: BLE001
        logger.exception("[PYTHON_EXECUTE] 异常 step=%s", current_step)
        summary = f"PYTHON_EXECUTION 异常: {type(exc).__name__} - {exc}"
        print(f"  [PYTHON_EXECUTE] 异常（不中断流程）：{summary}")
        # 故意不清空 PYTHON_EXECUTION_RESULT，保留之前的成功结果
        return {
            StateKey.EXECUTION_OUTPUT: {f"step_{current_step}_pyexec_error": summary}
        }
