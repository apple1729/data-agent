"""数据库连接。

对应 Java 版 application.yml 里的 spring.datasource 配置 + MyBatis 的 SqlSession。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import settings

# 连接池配置：开发期够用即可
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,          # 想看 SQL 就改成 True
    pool_pre_ping=True,  # 连接断了自动重连，避免长时间空闲后第一次查询报错
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
