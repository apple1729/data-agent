"""把数据库实体转成"用于向量化的文档"。

对应 Java 版的 DocumentMapperUtil。

规则：text 是送去算向量的文本，metadata 是检索时用来过滤的标签。
**metadata 里的 vectorType 和 databaseId 是关键**——少了它们，
检索会跨库、跨类型乱捞。
"""

from dataclasses import dataclass, field

from app.db.models import DbColumn, DbTable, GlossaryKnowledge, QuestionKnowledge

# 四种向量类型。取值必须和 Java 版一致，否则已有的数据对不上。
VECTOR_TYPE_TABLE = "table"
VECTOR_TYPE_COLUMN = "column"
VECTOR_TYPE_GLOSSARY = "glossaryKnowledge"
VECTOR_TYPE_QUESTION = "questionKnowledge"


@dataclass
class VectorDocument:
    """一条待入库的向量文档。"""

    text: str
    metadata: dict = field(default_factory=dict)


def from_table(table: DbTable) -> VectorDocument:
    """表 → 文档。用可读表名做文本（学习期用这个够了）。"""
    return VectorDocument(
        text=table.description or table.name,
        metadata={
            "vectorType": VECTOR_TYPE_TABLE,
            "databaseId": table.database_id,
            "tableId": str(table.id),
        },
    )


def from_column(column: DbColumn, table: DbTable) -> VectorDocument:
    """列 → 文档。用列的可读名做文本。"""
    return VectorDocument(
        text=column.description or column.name,
        metadata={
            "vectorType": VECTOR_TYPE_COLUMN,
            "databaseId": table.database_id,
            "tableId": str(table.id),
            "columnId": str(column.id),
        },
    )


def from_glossary(item: GlossaryKnowledge) -> VectorDocument:
    """业务术语 → 文档。文本拼成一句完整的话，语义更清楚。"""
    text = f"业务名词: {item.term}, 说明: {item.description}, 同义词: {item.synonyms or ''}"
    return VectorDocument(
        text=text,
        metadata={
            "vectorType": VECTOR_TYPE_GLOSSARY,
            "databaseId": item.database_id,
            "businessTermId": str(item.id),
        },
    )


def from_question(item: QuestionKnowledge) -> VectorDocument:
    """历史问答 → 文档。**只把问题送去向量化**，答案靠 id 回库取。

    这是 Java 版的设计：向量库里只存"问题"，
    召回后再用 knowledgeId 回 question_knowledge 拿完整问答。
    """
    return VectorDocument(
        text=item.question,
        metadata={
            "vectorType": VECTOR_TYPE_QUESTION,
            "databaseId": item.database_id,
            "knowledgeId": str(item.id),
        },
    )
