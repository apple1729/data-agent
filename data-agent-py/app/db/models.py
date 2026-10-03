"""5 张业务表的模型。

严格对齐 database.sql 里的表结构（列名、类型、唯一约束、外键）。
对应 Java 版的 entity/dataset/*.java + mapper/*.xml。
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DbTable(Base):
    """业务库里的表。对应 Java 的 DbTable。"""

    __tablename__ = "db_table"
    __table_args__ = (
        UniqueConstraint("database_id", "name", name="uq_db_table_name_database"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # description 存的是 BIRD 里那个"可读表名"（带空格，如 "gas stations"），
    # 向量化时用这个文本做 embedding，比原始表名語義更好。
    description: Mapped[str] = mapped_column(Text, nullable=False)
    database_id: Mapped[str] = mapped_column(String(255), nullable=False)

    columns: Mapped[list["DbColumn"]] = relationship(
        back_populates="table", cascade="all, delete-orphan"
    )


class DbColumn(Base):
    """业务库里的列。对应 Java 的 DbColumn。"""

    __tablename__ = "db_column"
    __table_args__ = (
        UniqueConstraint("table_id", "name", name="uq_db_column_table_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_primary_key: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("db_table.id", ondelete="CASCADE"), nullable=False
    )

    table: Mapped[DbTable] = relationship(back_populates="columns")


class DbForeignKey(Base):
    """表和表之间的外键关系。对应 Java 的 DbForeignKey。"""

    __tablename__ = "db_foreign_key"
    __table_args__ = (
        UniqueConstraint(
            "source_column_id", "target_column_id", name="uq_db_foreign_key_source_target"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_column_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("db_column.id", ondelete="CASCADE"), nullable=False
    )
    target_column_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("db_column.id", ondelete="CASCADE"), nullable=False
    )

    source_column: Mapped[DbColumn] = relationship(foreign_keys=[source_column_id])
    target_column: Mapped[DbColumn] = relationship(foreign_keys=[target_column_id])


class GlossaryKnowledge(Base):
    """业务术语 / 计算口径。对应 Java 的 GlossaryKnowledge。

    注意：BIRD 的 evidence 里没有单独的"术语名"，所以 term 存空串，
    真正的知识全在 description 里——这跟 Java 版的做法一致。
    """

    __tablename__ = "glossary_knowledge"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    database_id: Mapped[str] = mapped_column(String(255), nullable=False)
    term: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    synonyms: Mapped[str | None] = mapped_column(String(255), nullable=True)


class QuestionKnowledge(Base):
    """历史问答（问题 → 标准 SQL）。对应 Java 的 QuestionKnowledge。"""

    __tablename__ = "question_knowledge"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    database_id: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
