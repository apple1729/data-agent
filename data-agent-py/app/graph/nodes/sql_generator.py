"""SQL 生成节点。

根据"当前计划步骤里的 instruction" + "表结构" + "证据"，让大模型写出 SQL。

【三个容易踩的点】
  1. instruction 要从 step.tool_parameters 里取，不是顶层的同名字段
     （原项目顶层那套字段是死代码，从来不读）
  2. prompt 是当 **system 消息**发的，不是 user——Java 写的是 .system(sqlPrompt)
  3. 模型爱把 SQL 包在 ```sql ... ``` 里，要剥壳再存

【出错时不往上抛】
  出错就写进状态，让下一轮 Supervisor 读到、决定重试还是换路子。
  直接抛异常会让整张图崩掉，用户看到的就是一个失败的任务。

对应 Java 的 SqlGeneratorNode。
"""

import asyncio
import logging

from app.domain.schema import Schema
from app.graph.state import AgentState, StateKey
from app.llm import client, markdown, prompts
from app.llm.dto import Plan

logger = logging.getLogger(__name__)

# Java 里把这个方言写死成 "mysql"。
# 而 BIRD 的物理库其实是 SQLite——不过 SQLite 对反引号是兼容的，
# 所以实际能跑。这里照抄原样，不自己改。
DIALECT = "mysql"


async def sql_generator_node(state: AgentState) -> dict:
    current_step = state.get(StateKey.CURRENT_STEP, 1)

    try:
        plan = Plan.model_validate_json(state.get(StateKey.PLAN, "{}"))
        step = plan.get_step(current_step)
        instruction = (step.tool_parameters.instruction or "").strip()
        if not instruction:
            raise ValueError("SQL 生成步骤的 instruction 为空")

        schema = Schema.model_validate_json(
            state.get(StateKey.TABLE_RELATION, "{}")
        )
        prompt = prompts.render(
            "new-sql-generate",
            {
                "dialect": DIALECT,
                "question": state.get(StateKey.REWRITE_QUERY, ""),
                "schema_info": schema.build_scheme_prompt(),
                "evidence": state.get(StateKey.EVIDENCE, ""),
                "execution_description": instruction,
            },
        )

        # 注意第二个位置参数是 system：Java 用的是 .system(sqlPrompt)
        raw = await asyncio.to_thread(client.chat, None, prompt)
        sql = markdown.extract_raw_text(raw).strip()
        if not sql:
            raise ValueError("生成的 SQL 为空")

        print(f"  [SQL_GENERATE] 第 {current_step} 步生成 SQL：")
        for line in sql.splitlines()[:6]:
            print(f"      {line}")

        return {
            StateKey.SQL_GENERATION_RESULT: sql,
            StateKey.EXECUTION_OUTPUT: {f"step_{current_step}": f"[SQL 生成] {sql}"},
        }

    except Exception as exc:  # noqa: BLE001 - 故意兜住所有异常，不让图崩
        logger.exception("[SQL_GENERATE] 生成失败 step=%s", current_step)
        summary = f"SQL_GENERATION 失败: {type(exc).__name__} - {exc}"
        print(f"  [SQL_GENERATE] 失败（不中断流程）：{summary}")

        # 清空旧值，避免下游误用上一轮的 SQL；
        # 同时写两个错误 key（照抄 Java 的设计）：
        #   step_N_error        → Supervisor 做通用失败判定
        #   step_N_sqlgen_error → 单独保留根因，免得被执行阶段的错误覆盖
        return {
            StateKey.SQL_GENERATION_RESULT: "",
            StateKey.EXECUTION_OUTPUT: {
                f"step_{current_step}_error": summary,
                f"step_{current_step}_sqlgen_error": summary,
            },
        }
