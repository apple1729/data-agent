"""从模型返回的 markdown 里把代码块内容抠出来。

对应 Java 的 MarkdownParserUtil。

【为什么需要它】
  模型经常不听话地把 SQL 包在 ```sql ... ``` 里，前前后后还带解释文字。
  直接拿去执行会语法错误，所以要先剥壳。
"""

import re


def extract_raw_text(markdown_code: str) -> str:
    """提取代码块内容（保留换行）。

    逻辑和 Java 版一致：找第一个 ```（可能是 4 个及以上），
    跳过语言标识那一行，一直取到对应的结束标记。
    没找到代码块就原样返回。
    """
    if not markdown_code:
        return markdown_code

    match = re.search(r"`{3,}", markdown_code)
    if not match:
        return markdown_code

    delimiter = match.group(0)
    content_start = markdown_code.find("\n", match.end())
    if content_start == -1:
        return markdown_code[match.end() :]
    content_start += 1   # 跳过换行本身

    end = markdown_code.find(delimiter, content_start)
    if end == -1:
        return markdown_code[content_start:]
    return markdown_code[content_start:end]
