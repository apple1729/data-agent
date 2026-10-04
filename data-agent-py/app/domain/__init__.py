"""领域模型：业务数据结构的定义。

和另外两个 models 区分开：
  app/db/models.py   → 数据库表的映射（SQLAlchemy，管存取的）
  app/llm/dto.py     → 大模型输出格式（管解析的）
  app/domain/        → 业务概念本身（比如"数据库结构"这个对象）
"""
