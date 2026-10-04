"""Prompt 模板加载与渲染。

对应 Java 版 PromptManager。

【模板在哪】app/prompts/*.st（从 Java 项目的 resources/prompts 复制来的）

【占位符规则】
  模板里用 {变量名} 表示要替换的地方，比如 {latest_query}。

  但有个坑：模板里的 JSON 示例用了 **转义写法** \\{ 和 \\}，
  表示"这里是字面的花括号，不要当成占位符"：

      \\{"standalone_query": "查询投诉率"\\}

  这是 Spring AI 的 StringTemplate 语法。Python 这边必须先把它们还原成
  普通花括号，否则替换逻辑会出错。

【找不到的变量怎么办】
  原样保留。这样如果我把变量名拼错了，跑出来的 prompt 里会赫然出现
  {latest_query} 这种东西，一眼就能发现——比静默替换成空字符串安全得多。
"""

import re
from functools import lru_cache
from pathlib import Path

# app/prompts/（本文件在 app/llm/ 下，往上两层到 app/）
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# 只匹配 {单词}，且要求前面的字符不是反斜杠（排除 \{ 这种情况）
_PLACEHOLDER = re.compile(r"(?<!\\)\{(\w+)\}")


@lru_cache(maxsize=None)
def load(name: str) -> str:
    """读取模板原文。带缓存，同一个模板只读一次磁盘。"""
    path = PROMPTS_DIR / f"{name}.st"
    if not path.exists():
        available = sorted(p.stem for p in PROMPTS_DIR.glob("*.st"))
        raise FileNotFoundError(f"找不到模板 {name}.st。可用的有：{available}")
    return path.read_text(encoding="utf-8")


def render(name: str, variables: dict | None = None) -> str:
    """读取模板并把 {变量} 替换掉，返回最终的 prompt 文本。"""
    text = load(name)
    variables = variables or {}

    # 第一步：把模板里的字面花括号还原（\{ -> {）
    text = text.replace("\\{", "{").replace("\\}", "}")

    # 第二步：替换占位符
    def _replace(match: re.Match) -> str:
        key = match.group(1)
        if key in variables:
            return str(variables[key])
        return match.group(0)  # 变量没传 → 原样保留，方便发现拼写错误

    return _PLACEHOLDER.sub(_replace, text)


def available() -> list[str]:
    """列出所有可用模板名（调试用）。"""
    return sorted(p.stem for p in PROMPTS_DIR.glob("*.st"))
