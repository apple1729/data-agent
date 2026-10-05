"""SQL 执行节点。

拿上一步生成的 SQL 去 BIRD 的 SQLite 库上**真跑**，把结果集写回状态。

【一个容易被忽略的关键动作】
  执行成功后要把 SQL **回填进当前计划步骤**（tool_parameters.sql_query），
  再把整个计划序列化回状态。
  否则下游的 Supervisor 和 ReportGenerator 反序列化计划时看到的是空 SQL，
  报告里就会出现"没有 SQL"的尴尬。

【出错时不清空旧结果】
  多 SQL 场景下（Supervisor 可能派好几轮 SQL），
  某一步失败不应该把前面成功的查询结果抹掉——那些数据出报告还要用。
  所以只追加错误标记，不动 SQL_EXECUTION_RESULT。

对应 Java 的 SqlExecuteNode。
"""

import asyncio
import logging

from app.db import business_db
from app.domain.result_set import (
    SqlExecuteResult,
    build_display_spec,
    build_result_set,
)
from app.graph.state import AgentState, StateKey
from app.llm.dto import Plan

logger = logging.getLogger(__name__)


async def sql_execute_node(state: AgentState) -> dict:
    current_step = state.get(StateKey.CURRENT_STEP, 1)
    sql = (state.get(StateKey.SQL_GENERATION_RESULT) or "").strip()

    # ---- 上游没生成 SQL：跳过，但**不要**写 step_N_error ----
    # 因为 SqlGeneratorNode 已经把真正的失败原因写进 step_N_sqlgen_error 了，
    # 这里再写一个通用的 error 会把它覆盖掉，Supervisor 就看不到根因。
    if not sql:
        print(f"  [SQL_EXECUTE] 第 {current_step} 步：上游 SQL 为空，跳过")
        return {
            StateKey.EXECUTION_OUTPUT: {
                f"step_{current_step}_sqlexec_skipped": (
                    "SQL_EXECUTION 跳过：上游未生成有效 SQL"
                    f"（根因见 step_{current_step}_sqlgen_error）"
                )
            }
        }

    database_id = state.get(StateKey.DATABASE_ID, "")

    try:
        result_set, display = await asyncio.to_thread(_run_sql, database_id, sql)

        # ★ 把 SQL 回填进计划，否则下游看不到
        plan = Plan.model_validate_json(state.get(StateKey.PLAN, "{}"))
        plan.get_step(current_step).tool_parameters.sql_query = sql

        print(
            f"  [SQL_EXECUTE] 第 {current_step} 步：{len(result_set.data)} 行 × "
            f"{len(result_set.column)} 列"
        )
        for row in result_set.data[:3]:
            print(f"      {row}")

        execute_result = SqlExecuteResult(resultSet=result_set, display=display)
        return {
            StateKey.PLAN: plan.model_dump_json(),
            StateKey.SQL_EXECUTION_RESULT: execute_result.model_dump(),
            StateKey.EXECUTION_OUTPUT: {
                f"step_{current_step}": result_set.model_dump_json()
            },
        }

    except Exception as exc:  # noqa: BLE001 - 兜底，让 Supervisor 决定重试还是换路子
        logger.exception("[SQL_EXECUTE] 执行失败 step=%s", current_step)
        summary = (
            f"SQL_EXECUTION 失败: {type(exc).__name__} - {exc}"
            f" | 失败的 SQL: {sql}"
        )
        print(f"  [SQL_EXECUTE] 失败（不中断流程）：{type(exc).__name__} - {exc}")

        # 两个 key 都写：通用的给 Supervisor 判定失败，阶段化的保留根因
        # 注意：故意不动 SQL_EXECUTION_RESULT，保留之前成功的查询结果
        return {
            StateKey.EXECUTION_OUTPUT: {
                f"step_{current_step}_error": summary,
                f"step_{current_step}_sqlexec_error": summary,
            }
        }


def _run_sql(database_id: str, sql: str):
    """连 SQLite 执行 SQL，返回（结果集, 展示配置）。

    同步函数，由节点用 to_thread 调用——SQLite 查询可能很慢，
    直接跑会卡住整个事件循环。
    """
    with business_db.connect(database_id) as conn:
        cursor = conn.cursor()
        cursor.execute(sql)

        # 只有 SELECT 才有列信息。写成 INSERT/UPDATE 之类的一律拒绝——
        # 这个系统只读业务库，不允许改数据。
        if cursor.description is None:
            raise ValueError("只允许执行查询语句（SELECT）")

        rows = cursor.fetchmany(1000)   # 最多 1000 行，和 Java 一致
        result_set = build_result_set(cursor.description, rows)

    return result_set, build_display_spec(result_set)
