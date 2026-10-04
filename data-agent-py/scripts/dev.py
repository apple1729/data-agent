"""开发调试工具。

阶段 3 要反复验证各个节点，这个脚本提供统一的入口，
省得每次都临时写一段代码。

用法：
    python -m scripts.dev chat "用一句话说明什么是SQL"
    python -m scripts.dev prompt planner
    python -m scripts.dev node scheme_recall
    python -m scripts.dev nodes              # 列出所有节点
"""

import argparse
import asyncio
import json

from app.graph import nodes as all_nodes
from app.graph.state import StateKey


# 单独跑节点时用的默认输入：挑一个 BIRD 里的真实问题
DEFAULT_INPUT = "highest eligible free rate for K-12 students in Alameda County"
DEFAULT_DB = "california_schools"


def build_default_state() -> dict:
    """造一份"像是上一批节点刚跑完"的状态，让任意节点都能单独试。"""
    return {
        StateKey.USER_INPUT: DEFAULT_INPUT,
        StateKey.DATABASE_ID: DEFAULT_DB,
        StateKey.MULTI_TURN_CONTEXT: "(无)",
        StateKey.REWRITE_QUERY: DEFAULT_INPUT,
        StateKey.EVIDENCE: "(无)",
        StateKey.TABLE_SCHEME: [],
        StateKey.COLUMN_SCHEME: [],
        StateKey.TABLE_RELATION: "{}",
        StateKey.CURRENT_STEP: 1,
        StateKey.SUPERVISOR_ITERATION: 0,
    }


def cmd_chat(args) -> None:
    """测聊天模型通不通。"""
    from app.llm import client

    print(f"提问：{args.text}")
    answer = client.chat(args.text)
    print(f"回答：{answer}")


def cmd_prompt(args) -> None:
    """看模板渲染后的样子（不调模型，免费）。"""
    from app.llm import prompts

    variables = {}
    for pair in args.vars or []:
        if "=" in pair:
            k, v = pair.split("=", 1)
            variables[k] = v

    text = prompts.render(args.name, variables)
    print(f"===== {args.name}.st 渲染结果（{len(text)} 字符）=====")
    print(text)


def cmd_nodes(_args) -> None:
    print("可用的节点：")
    for name in sorted(all_nodes.__all__):
        print("  ", name.removesuffix("_node"))


def cmd_doctor(_args) -> None:
    """体检：逐步检查每一环通不通，卡在哪一步一眼就能看出来。"""
    import time

    from sqlalchemy import text as sql_text

    from app import settings
    from app.db.session import engine
    from app.retrieval import embeddings, vector_store

    def step(name, fn):
        print(f"[ .. ] {name}", flush=True)
        started = time.time()
        try:
            result = fn()
            print(f"[ OK ] {name}  ({time.time() - started:.2f}s)  {result}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {name}  ({time.time() - started:.2f}s)  "
                  f"{type(exc).__name__}: {exc}", flush=True)

    step("读配置", lambda: f"PG={settings.PG_HOST}:{settings.PG_PORT}/{settings.PG_DATABASE} "
                          f"CHAT={settings.CHAT_MODEL} EMB={settings.EMBEDDING_MODEL}")

    def ping_db():
        with engine.connect() as conn:
            return conn.execute(sql_text("SELECT 1")).scalar_one()

    step("连数据库", ping_db)
    step("数向量条数", vector_store.count)
    step("调 embedding 接口", lambda: f"维度={len(embeddings.embed_one('ping'))}")

    def search_once():
        rows = vector_store.search_by_text(
            "highest eligible free rate", "california_schools", "table", 3
        )
        return f"召回 {len(rows)} 条，首条={rows[0]['content'][:30] if rows else '-'}"

    step("向量检索", search_once)


def cmd_schema(args) -> None:
    """把某个库的完整结构渲染出来，验证 Schema 模型和查询。"""
    from app.db import schema_repo
    from app.domain.schema import (
        DbColumnView,
        DbForeignKeyView,
        DbTableView,
        ForeignKeyColumnView,
        ForeignKeyTableView,
        Schema,
    )

    tables = schema_repo.find_all_tables_with_columns(args.database)
    foreign_keys = schema_repo.find_foreign_keys_by_database(args.database)

    schema = Schema(
        databaseId=args.database,
        dbTables=[
            DbTableView(
                name=t.name,
                columns=[
                    DbColumnView(
                        name=c.name,
                        type=c.type,
                        description=c.description,
                        isPrimaryKey=c.is_primary_key,
                    )
                    for c in t.columns
                ],
            )
            for t in tables
        ],
        dbForeignKeys=[
            DbForeignKeyView(
                sourceColumn=ForeignKeyColumnView(
                    name=fk.source_column.name,
                    dbTable=ForeignKeyTableView(name=fk.source_column.table.name),
                ),
                targetColumn=ForeignKeyColumnView(
                    name=fk.target_column.name,
                    dbTable=ForeignKeyTableView(name=fk.target_column.table.name),
                ),
            )
            for fk in foreign_keys
        ],
    )

    print(f"库 {args.database}：表 {len(schema.dbTables)} 张 / "
          f"外键 {len(schema.dbForeignKeys)} 条")
    print()
    rendered = schema.build_scheme_prompt()
    print(f"===== 渲染结果（共 {len(rendered)} 字符）=====")
    print(rendered if args.full or len(rendered) <= 2500
          else rendered[:2500] + f"\n...(共 {len(rendered)} 字符，加 --full 看全部)")


def cmd_node(args) -> None:
    """单独跑一个节点，看它真实产出什么。"""
    func = getattr(all_nodes, f"{args.name}_node", None)
    if func is None:
        raise SystemExit(f"没有这个节点：{args.name}。用 `python -m scripts.dev nodes` 看全部")

    state = build_default_state()
    print(f"===== 单独运行节点：{args.name} =====")
    print(f"输入 state 的关键字段：")
    print(f"  input          = {state[StateKey.USER_INPUT]!r}")
    print(f"  databaseId     = {state[StateKey.DATABASE_ID]!r}")
    print()

    result = asyncio.run(func(state))

    print()
    print("节点返回的字段：")
    for key, value in (result or {}).items():
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
        if not args.full and len(text) > 600:
            text = text[:600] + f"...(共 {len(text)} 字符，加 --full 看全部)"
        print(f"  --- {key} ---")
        print(f"  {text}")


def cmd_chain(args) -> None:
    """按顺序跑几个节点，把状态一路传下去（模拟图的一部分）。

    用途：后面的节点依赖前面节点的产出，单独跑会因为输入为空而没结果。
    比如 table_relation 需要 scheme_recall 先召回出候选表。

    用法：
        python -m scripts.dev chain scheme_recall table_relation
        python -m scripts.dev chain evidence_recall scheme_recall table_relation
    """
    state = build_default_state()
    for name in args.names:
        func = getattr(all_nodes, f"{name}_node", None)
        if func is None:
            raise SystemExit(f"没有这个节点：{name}")

        print(f"\n{'=' * 20} 跑节点 {name} {'=' * 20}")
        result = asyncio.run(func(state)) or {}

        # 注意：EXECUTION_OUTPUT 要"累加"而不是"覆盖"，
        # 和真实图里的 reducer 行为保持一致，否则测出来的东西不准。
        for key, value in result.items():
            if key == StateKey.EXECUTION_OUTPUT and isinstance(value, dict):
                state[key] = {**(state.get(key) or {}), **value}
            else:
                state[key] = value

        print(f"  → 写回字段：{list(result.keys())}")

    print(f"\n{'=' * 20} 最终状态 {'=' * 20}")
    for key, value in state.items():
        # TABLE_RELATION 是一大坨 JSON，打摘要比打原文有用
        if key == StateKey.TABLE_RELATION and isinstance(value, str):
            try:
                parsed = json.loads(value)
                tables = [t["name"] for t in parsed.get("dbTables", [])]
                cols = sum(len(t.get("columns", [])) for t in parsed.get("dbTables", []))
                fks = [
                    f"{f['sourceColumn']['dbTable']['name']}.{f['sourceColumn']['name']}"
                    f" = {f['targetColumn']['dbTable']['name']}.{f['targetColumn']['name']}"
                    for f in parsed.get("dbForeignKeys", [])
                ]
                print(f"\n--- {key}（摘要）---")
                print(f"  表：{tables}（共 {cols} 列）")
                print(f"  外键：{fks}")
                if args.full:
                    print(f"  原始 JSON：{value}")
                continue
            except (ValueError, KeyError, TypeError):
                pass

        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
        if not args.full and len(text) > 400:
            text = text[:400] + f"...(共 {len(text)} 字符)"
        print(f"\n--- {key} ---")
        print(f"{text}")


def main() -> None:
    parser = argparse.ArgumentParser(description="开发调试工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_chat = sub.add_parser("chat", help="测聊天模型")
    p_chat.add_argument("text", help="要问的话")
    p_chat.set_defaults(func=cmd_chat)

    p_prompt = sub.add_parser("prompt", help="看模板渲染结果")
    p_prompt.add_argument("name", help="模板名（不带 .st）")
    p_prompt.add_argument("vars", nargs="*", help="变量，形如 key=value")
    p_prompt.set_defaults(func=cmd_prompt)

    p_node = sub.add_parser("node", help="单独跑一个节点")
    p_node.add_argument("name", help="节点名（不带 _node 后缀）")
    p_node.add_argument("--full", action="store_true", help="完整打印返回值，不截断")
    p_node.set_defaults(func=cmd_node)

    p_nodes = sub.add_parser("nodes", help="列出所有节点")
    p_nodes.set_defaults(func=cmd_nodes)

    p_chain = sub.add_parser("chain", help="按顺序跑几个节点，状态接力传递")
    p_chain.add_argument("names", nargs="+", help="节点名，按执行顺序写")
    p_chain.add_argument("--full", action="store_true", help="不截断输出")
    p_chain.set_defaults(func=cmd_chain)

    p_doctor = sub.add_parser("doctor", help="体检：检查数据库/embedding/检索是否正常")
    p_doctor.set_defaults(func=cmd_doctor)

    p_schema = sub.add_parser("schema", help="渲染某个库的完整结构（测 Schema 模型）")
    p_schema.add_argument("database", nargs="?", default=DEFAULT_DB, help="库名")
    p_schema.add_argument("--full", action="store_true", help="不截断")
    p_schema.set_defaults(func=cmd_schema)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
