"""知识表的查询。

对应 Java 的 QuestionKnowledgeMapper / GlossaryKnowledgeMapper。

【为什么需要它】
  向量库里**只存了问题的文本**（不存答案），
  所以要拿完整问答得用 metadata 里的 knowledgeId 回表查。
  这是原项目的设计——向量库只负责"找到是哪一条"。
"""

import uuid

from app.db.models import QuestionKnowledge
from app.db.session import SessionLocal


def find_questions_by_ids(ids: list[uuid.UUID]) -> list[QuestionKnowledge]:
    """按 id 批量取历史问答。"""
    if not ids:
        return []
    with SessionLocal() as session:
        return (
            session.query(QuestionKnowledge)
            .filter(QuestionKnowledge.id.in_(ids))
            .all()
        )
