"""证据召回节点。

四步：
  1. 用大模型把"多轮上下文 + 用户最新问题"改写成一句独立完整的问句
     （多轮对话里会有"那它呢？"这种指代不清的话，不改写没法检索）
  2. 拿改写后的问句去向量库召回两类东西：业务术语、历史问答
  3. 历史问答在向量库里**只存了问题**，要拿 knowledgeId 回表取完整问答
  4. 用两个模板拼成一段 Evidence 文本

对应 Java 的 EvidenceRecallNode。
"""

import asyncio
import logging
import uuid

from app.db import knowledge_repo
from app.graph.state import AgentState, StateKey
from app.llm import client, prompts, structured
from app.llm.dto import EvidenceQueryRewrite
from app.retrieval import vector_store
from app.retrieval.document_mapper import VECTOR_TYPE_GLOSSARY, VECTOR_TYPE_QUESTION

logger = logging.getLogger(__name__)

# 条数照抄 Java
GLOSSARY_TOP_K = 4
QUESTION_TOP_K = 4


async def evidence_recall_node(state: AgentState) -> dict:
    user_input = state.get(StateKey.USER_INPUT, "")
    database_id = state.get(StateKey.DATABASE_ID, "")
    multi_turn = state.get(StateKey.MULTI_TURN_CONTEXT, "(无)")

    # ---- 1) 改写问题 ----
    rewrite_prompt = prompts.render(
        "evidence-query-rewrite",
        {
            "latest_query": user_input,
            "multi_turn": multi_turn,
            "format": structured.format_hint(EvidenceQueryRewrite),
        },
    )
    raw = await asyncio.to_thread(client.chat, rewrite_prompt)
    rewrite_query = structured.parse(raw, EvidenceQueryRewrite).standalone_query.strip()
    if not rewrite_query:
        raise ValueError(f"问题改写失败，模型返回：{raw[:200]}")
    print(f"  [EVIDENCE_RECALL] 改写后 → {rewrite_query!r}")

    # ---- 2) 两路检索 ----
    glossaries = await asyncio.to_thread(
        vector_store.search_by_text,
        rewrite_query,
        database_id,
        VECTOR_TYPE_GLOSSARY,
        GLOSSARY_TOP_K,
    )
    question_docs = await asyncio.to_thread(
        vector_store.search_by_text,
        rewrite_query,
        database_id,
        VECTOR_TYPE_QUESTION,
        QUESTION_TOP_K,
    )

    # ---- 3) 历史问答回表取完整内容 ----
    knowledge_ids: list[uuid.UUID] = []
    for doc in question_docs:
        raw_id = (doc.get("metadata") or {}).get("knowledgeId")
        if not raw_id:
            continue
        try:
            knowledge_ids.append(uuid.UUID(str(raw_id)))
        except ValueError:
            logger.warning("跳过无法解析的 knowledgeId: %r", raw_id)

    questions = await asyncio.to_thread(
        knowledge_repo.find_questions_by_ids, knowledge_ids
    )

    # ---- 4) 拼证据 ----
    glossary_text = "\n".join(item["content"] for item in glossaries)
    question_text = "\n".join(
        f"来源：{q.database_id} Q: {q.question} A: {q.answer}" for q in questions
    )

    if not glossary_text and not question_text:
        evidence = "无"
    else:
        evidence = "\n".join(
            [
                prompts.render(
                    "business-knowledge",
                    {"businessKnowledge": glossary_text or "无"},
                ),
                prompts.render(
                    "agent-knowledge", {"agentKnowledge": question_text or "无"}
                ),
            ]
        )

    print(
        f"  [EVIDENCE_RECALL] 召回：术语 {len(glossaries)} 条 / "
        f"历史问答 {len(questions)} 条"
    )

    return {
        StateKey.REWRITE_QUERY: rewrite_query,
        StateKey.EVIDENCE: evidence,
    }
