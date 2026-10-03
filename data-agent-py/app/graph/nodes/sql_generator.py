"""SQL 生成节点。

真实现要做的（阶段 3）：
  用"表结构 + 证据 + 改写后的问题"让 LLM 写出 SQL 语句。
  输出要剥掉 markdown 代码块标记（```sql ... ```）。

对应 Java 的 SqlGeneratorNode。
"""

from app.graph.state import AgentState, StateKey


async def sql_generator_node(state: AgentState) -> dict:
    step = state.get(StateKey.CURRENT_STEP, 1)
    print(f"  [SQL_GENERATE] 第 {step} 步：生成 SQL")

    sql = f"SELECT '[假] 第{step}步的查询' AS result"
    return {
        StateKey.SQL_GENERATION_RESULT: sql,
        StateKey.EXECUTION_OUTPUT: {f"step_{step}": f"[假] SQL: {sql}"},
    }
