"""库表结构的查询。

对应 Java 的 DbTableMapper / DbColumnMapper / DbForeignKeyMapper。

table_relation 节点要用到两个查询：
  1. 一个库的所有外键（用来做"外键扩展"，把桥表补进来）
  2. 一批表 + 它们的列（用来拼最终的 schema）
"""

import uuid

from sqlalchemy.orm import joinedload, selectinload

from app.db.models import DbColumn, DbForeignKey, DbTable
from app.db.session import SessionLocal


def find_foreign_keys_by_database(database_id: str) -> list[DbForeignKey]:
    """取一个库的所有外键，两端关联的列和表一并加载出来。

    【为什么要 joinedload】
      外键对象本身只存了两个列的 id。要渲染成
      "satscores.cdsc = schools.CDSCode" 还得知道列名和表名。
      不预加载的话，出了 session 再访问这些属性会报错（懒加载失效）。
    """
    with SessionLocal() as session:
        return (
            session.query(DbForeignKey)
            .join(DbColumn, DbForeignKey.source_column_id == DbColumn.id)
            .join(DbTable, DbColumn.table_id == DbTable.id)
            .filter(DbTable.database_id == database_id)
            .options(
                joinedload(DbForeignKey.source_column).joinedload(DbColumn.table),
                joinedload(DbForeignKey.target_column).joinedload(DbColumn.table),
            )
            .all()
        )


def find_tables_with_columns(table_ids: list[uuid.UUID]) -> list[DbTable]:
    """按 id 批量取表，连它们的列一起。"""
    if not table_ids:
        return []
    with SessionLocal() as session:
        return (
            session.query(DbTable)
            .options(selectinload(DbTable.columns))
            .filter(DbTable.id.in_(table_ids))
            .all()
        )


def find_all_tables_with_columns(database_id: str) -> list[DbTable]:
    """取一个库的全部表（含列）。调试和全量比对时用。"""
    with SessionLocal() as session:
        return (
            session.query(DbTable)
            .options(selectinload(DbTable.columns))
            .filter(DbTable.database_id == database_id)
            .order_by(DbTable.name)
            .all()
        )


def find_tables_by_database_and_names(database_id: str, names: list[str]) -> list[DbTable]:
    """按表名批量取表（含列）。table_relation 最后一步用。"""
    if not names:
        return []
    with SessionLocal() as session:
        return (
            session.query(DbTable)
            .options(selectinload(DbTable.columns))
            .filter(DbTable.database_id == database_id, DbTable.name.in_(names))
            .all()
        )
