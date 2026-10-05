"""Python 结果分析节点。

把 Python 执行出来的数字交给大模型，让它翻译成自然语言结论。

结论写进 `EXECUTION_OUTPUT` 的 `step_N_analysis` 键——
报告节点会把它作为"Python 分析结果"补充展示。

【什么时候跳过】
  · 上游没有执行结果（生成或执行失败了）
  · 上游执行结果为 success=False
  这两种情况都不该让大模型去"分析"一段报错文本，直接跳过，
  让 Supervisor 从轨迹里的 ❌ 标记看到失败。

对应 Java 的 PythonAnalyzeNode。
"""

import asyncio
import logging

from app.graph.state import AgentState, StateKey
from app.llm import client, prompts

logger = logging.getLogger(__name__)


async def python_analyze_node(state: AgentState) -> dict:
    current_step = state.get(StateKey.CURRENT_STEP, 1)

    try:
        python_output = state.get(StateKey.PYTHON_EXECUTION_RESULT)
        if not python_output:
            print(f"  [PYTHON_ANALYZE] 第 {current_step} 步：上游无执行结果，跳过")
            return {
                StateKey.EXECUTION_OUTPUT: {
                    f"step_{current_step}_pyanalyze_skipped": (
                        "PYTHON_ANALYSIS 跳过：上游 Python 执行结果缺失"
                    )
                }
            }

        if not python_output.get("success"):
            print(f"  [PYTHON_ANALYZE] 第 {current_step} 步：上游执行未成功，跳过")
            return {
                StateKey.EXECUTION_OUTPUT: {
                    f"step_{current_step}_pyanalyze_skipped": (
                        "PYTHON_ANALYSIS 跳过：Python 执行未成功"
                    )
                }
            }

        prompt = prompts.render(
            "python-analyze",
            {
                "python_output": python_output,
                "user_query": state.get(StateKey.REWRITE_QUERY, ""),
            },
        )
        analysis = (await asyncio.to_thread(client.chat, prompt)).strip()

        print(f"  [PYTHON_ANALYZE] 第 {current_step} 步：解读 {len(analysis)} 字符")

        # 只写自己这个 key，靠累加策略合并进全局结果，不影响其他步骤
        return {
            StateKey.EXECUTION_OUTPUT: {f"step_{current_step}_analysis": analysis}
        }

    except Exception as exc:  # noqa: BLE001
        logger.exception("[PYTHON_ANALYZE] 失败 step=%s", current_step)
        summary = f"PYTHON_ANALYSIS 失败: {type(exc).__name__} - {exc}"
        return {
            StateKey.EXECUTION_OUTPUT: {
                f"step_{current_step}_pyanalyze_error": summary
            }
        }
