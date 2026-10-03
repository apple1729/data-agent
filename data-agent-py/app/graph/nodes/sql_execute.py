"""SQL 执行节点。

真实现要做的（阶段 3）：
  拿生成的 SQL 去 BIRD 的 SQLite 库上真跑，最多取 1000 行，
  整理成 {column: [...], data: [...]} 的结构，并算出展示配置。

【阶段 3 的前置条件】需要下载 BIRD 的物理数据库文件（dev_databases.zip，
600MB+，被 .gitignore 排除），否则这一步没库可跑。

对应 Java 的 SqlExecuteNode。
"""

from app.graph.state import AgentState, StateKey


async def sql_execute_node(state: AgentState) -> dict:
    step = state.get(StateKey.CURRENT_STEP, 1)
    sql = state.get(StateKey.SQL_GENERATION_RESULT, "")
    print(f"  [SQL_EXECUTE] 第 {step} 步：执行 {sql!r}")

    fake_result = {"column": ["col1"], "data": [{"col1": "[假] 查询结果"}]}
    return {
        StateKey.SQL_EXECUTION_RESULT: fake_result,
        StateKey.EXECUTION_OUTPUT: {f"step_{step}": f"[假] SQL 执行结果：{fake_result}"},
    }
