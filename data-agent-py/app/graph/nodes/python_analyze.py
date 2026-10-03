"""Python 结果分析节点。

真实现要做的（阶段 3）：
  把 Python 的执行结果交给 LLM，让它翻译成自然语言结论，
  并把结论写进 EXECUTION_OUTPUT 的 `step_N_analysis` 键。

对应 Java 的 PythonAnalyzeNode。
"""

from app.graph.state import AgentState, StateKey


async def python_analyze_node(state: AgentState) -> dict:
    step = state.get(StateKey.CURRENT_STEP, 1)
    print(f"  [PYTHON_ANALYZE] 第 {step} 步：解读分析结果")

    return {
        StateKey.EXECUTION_OUTPUT: {
            f"step_{step}_analysis": "[假] 这段数字说明……（阶段 3 由 LLM 给出）"
        }
    }
