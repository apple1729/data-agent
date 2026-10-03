"""Python 代码执行节点。

真实现要做的（阶段 4）：
  把生成的代码丢进 Docker 沙箱里执行，拿 stdout / 报错。
  沙箱参数必须照抄原项目（--network none --cpus 1 --memory 512m 等），
  因为那是安全边界——代码是模型现写的，不能直接在本机跑。

对应 Java 的 PythonExecuteNode + SimplePythonExecutor。
"""

from app.graph.state import AgentState, StateKey


async def python_execute_node(state: AgentState) -> dict:
    step = state.get(StateKey.CURRENT_STEP, 1)
    code = state.get(StateKey.PYTHON_GENERATION_RESULT, "")
    print(f"  [PYTHON_EXECUTE] 第 {step} 步：沙箱执行（阶段 2 不真跑）")

    fake_output = {"success": True, "output": "[假] 分析代码的执行结果", "error": ""}
    return {
        StateKey.PYTHON_EXECUTION_RESULT: fake_output,
        StateKey.EXECUTION_OUTPUT: {f"step_{step}": f"[假] Python 执行结果：{fake_output}"},
    }
