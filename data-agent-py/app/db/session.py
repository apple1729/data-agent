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
    # 连不上时最多等 5 秒就报错。
    # 不加这个的话，如果 Docker 没启动，程序会**一直挂着不报错**
    # （没有任何进程监听端口时，Windows 会静默丢弃连接请求），
    # 排查起来会以为是自己代码卡死了。
    connect_args={"connect_timeout": 5},
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
