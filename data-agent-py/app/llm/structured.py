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

    容错处理：模型偶尔会不自觉地在 JSON 外面加解释文字或者 ``` 包裹，
    这里都剥掉。
    """
    return model.model_validate_json(_extract_json(text))


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
