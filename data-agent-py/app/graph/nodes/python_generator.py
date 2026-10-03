"""Python 代码生成节点。

真实现要做的（阶段 3）：
  当问题需要统计/画图时，让 LLM 写一段 Python 代码，
  输入是上游 SQL 的执行结果，输出要剥掉 markdown 标记。

对应 Java 的 PythonGeneratorNode。
"""

from app.graph.state import AgentState, StateKey


async def python_generator_node(state: AgentState) -> dict:
    step = state.get(StateKey.CURRENT_STEP, 1)
    print(f"  [PYTHON_GENERATE] 第 {step} 步：生成分析代码")

    code = "print('[假] 分析代码的执行结果')"
    return {
        StateKey.PYTHON_GENERATION_RESULT: code,
        StateKey.EXECUTION_OUTPUT: {f"step_{step}": f"[假] Python 代码：{code}"},
    }
