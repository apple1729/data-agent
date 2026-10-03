"""配置读取，对应 Java 版的 application.yml。

阶段 0 只用得到 HOST / PORT / AGENT_URL，其余的键先占好位，
等接数据库和大模型时直接取用。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


# ---------- 服务本身 ----------
HOST = os.getenv("APP_HOST", "0.0.0.0")
PORT = int(os.getenv("APP_PORT", "9933"))


# ---------- A2A 名片 ----------
# 注意 AGENT_URL 是「客户端来调我」的地址，不是「我监听」的地址。
# 默认写 Vite 代理地址（3500），和 Java 版名片一致，前端无需改动。
AGENT_URL = os.getenv("AGENT_URL", "http://localhost:3500/api/a2a/jsonrpc")
AGENT_NAME = os.getenv("AGENT_NAME", "sqlAgent")
AGENT_DESCRIPTION = os.getenv("AGENT_DESCRIPTION", "专业的SQL生成Agent")
AGENT_VERSION = os.getenv("AGENT_VERSION", "1.0")


# ---------- PostgreSQL（阶段 1 用）----------
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DATABASE = os.getenv("PG_DATABASE", "data_agent")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")

# SQLAlchemy 用的连接串。postgresql+psycopg 表示用 psycopg3 这个驱动。
DATABASE_URL = (
    f"postgresql+psycopg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"
)


# ---------- 大模型 / 向量（阶段 3 用）----------
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
CHAT_MODEL = os.getenv("CHAT_MODEL", "deepseek-v4-pro")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v4")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))

# DashScope 的 text-embedding-v4 一次请求最多处理 10 条文本，超过会报错
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "10"))

# 数据文件位置（自包含，不依赖 Java 项目）
DATA_DIR = PROJECT_ROOT / "data" / "bird"
