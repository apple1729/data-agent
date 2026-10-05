"""业务库（BIRD 的 SQLite 文件）连接。

对应 Java 的 SqliteSchemaDataSourceProvider。

【和 app/db/session.py 的区别】
  session.py      → 连 PostgreSQL，那里存的是"元数据"（表结构、术语、问答）
  business_db.py  → 连 SQLite，这里才是"真数据"（几千行几万行业务记录）

  生成 SQL 只需要元数据；**执行 SQL 才需要真数据**。
"""

import sqlite3
from pathlib import Path

from app import settings


def get_database_path(database_id: str) -> Path:
    """拼出某个库的 SQLite 文件路径。

    目录结构是 BIRD 数据集的约定：
        dev_databases/<库名>/<库名>.sqlite
    """
    return settings.BIRD_DB_DIR / database_id / f"{database_id}.sqlite"


def connect(database_id: str) -> sqlite3.Connection:
    """打开一个 SQLite 连接。"""
    path = get_database_path(database_id)
    if not path.exists():
        raise FileNotFoundError(
            f"找不到数据库文件：{path}\n"
            f"（需要先下载 BIRD 的 dev 数据集，见 README）"
        )
    return sqlite3.connect(path)


def available_databases() -> list[str]:
    """列出本地已有的库（调试用）。"""
    if not settings.BIRD_DB_DIR.exists():
        return []
    return sorted(p.name for p in settings.BIRD_DB_DIR.iterdir() if p.is_dir())
