"""让大模型按固定 JSON 格式输出，并解析回对象。

对应 Java 版的 BeanOutputConverter。

【为什么不直接用 OpenAI 的 json_schema 模式】
  百炼的 OpenAI 兼容模式对 response_format 的支持不完整。
  Java 版的做法是"把格式说明写进 prompt，再自己解析返回的文本"，
  这个更稳，所以照做。

【两步】
  format_hint(model)  → 生成一段"请按这个格式输出"的说明，塞进 prompt
  parse(text, model)  → 从模型返回的文本里抽出 JSON，解析成对象
"""

import json
import re
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def format_hint(model: type[BaseModel]) -> str:
    """生成格式要求，直接填进模板的 {format} 占位符里。"""
    schema = model.model_json_schema()
    return (
        "你的回答必须是一个 JSON 对象。不要输出任何解释文字，"
        "不要用 ```json 代码块包裹。格式如下（JSON Schema）：\n"
        + json.dumps(schema, ensure_ascii=False, indent=2)
    )


def parse(text: str, model: type[T]) -> T:
    """把模型输出解析成对象。

    【为什么要容错】
      模型输出的 JSON 经常不干净，实测遇到过的：
        · 外面包着 ```json ... ``` 或解释文字
        · 最后一个元素后面多一个逗号（尾逗号）
      这些都让严格 JSON 解析器报错。Java 版遇到同样问题会走兜底逻辑，
      在 Python 这边如果直接崩掉，整张图就挂了——所以这里做两层容错。
    """
    payload = _extract_json(text)
    try:
        return model.model_validate_json(payload)
    except Exception:
        # 退一步：清理掉尾逗号再试一次
        return model.model_validate_json(_strip_trailing_commas(payload))


def _extract_json(text: str) -> str:
    """剥掉 markdown 代码块和前后废话，只留 JSON 对象那一段。"""
    value = (text or "").strip()

    if value.startswith("```"):
        value = re.sub(r"^```[a-zA-Z]*\s*", "", value)
        value = re.sub(r"\s*```$", "", value).strip()

    start = value.find("{")
    end = value.rfind("}")
    if start >= 0 and end > start:
        return value[start : end + 1]
    return value


def _strip_trailing_commas(text: str) -> str:
    """去掉 `,}` 和 `,]` 这种多余逗号。

    模型很爱在最后一个元素后面多写一个逗号，标准 JSON 不允许。
    """
    return re.sub(r",(\s*[}\]])", r"\1", text)
