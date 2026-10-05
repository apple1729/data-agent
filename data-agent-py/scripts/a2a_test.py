"""通过 A2A 协议层测一次完整请求（最接近前端的调用方式）。

和 dev graph 的区别：
  dev graph  → 直接调图，绕过 A2A 层
  这个脚本   → 走 HTTP + JSON-RPC + SSE，和浏览器一模一样

用法：
    python -m scripts.a2a_test "highest eligible free rate for K-12 students"
    python -m scripts.a2a_test "问题" --db toxicology
"""

import argparse
import json

import httpx

DEFAULT_URL = "http://localhost:9933/a2a/jsonrpc"


def main() -> None:
    parser = argparse.ArgumentParser(description="通过 A2A 层测试")
    parser.add_argument("question", help="自然语言问题")
    parser.add_argument("--db", dest="database", default="california_schools")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--raw", action="store_true", help="打印原始 SSE 帧")
    args = parser.parse_args()

    body = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/stream",
        "params": {
            "message": {
                "messageId": "m1",
                "role": "user",
                "kind": "message",
                "metadata": {"databaseId": args.database},
                "parts": [{"kind": "text", "text": args.question}],
            }
        },
    }

    print(f"问题：{args.question}")
    print(f"库名：{args.database}")
    print()

    with httpx.stream("POST", args.url, json=body, timeout=600) as response:
        print(f"HTTP {response.status_code} | {response.headers.get('content-type')}")
        print()
        events = 0
        for raw_line in response.iter_lines():
            # SSE 协议里除了 data: 还有 event: / id: / 注释行（心跳），
            # 以及分隔用的空行——这些都不是 JSON，不能拿去解析。
            if not raw_line.startswith("data:"):
                if args.raw and raw_line.strip():
                    print(f"  [SSE] {raw_line[:100]}")
                continue

            payload = raw_line[len("data:") :].strip()
            if not payload:
                continue

            events += 1
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                print(f"  [解析失败] {payload[:150]}")
                continue

            if "error" in obj:
                print(f"  [ERROR] {obj['error']}")
                continue

            result = obj.get("result", {})
            kind = result.get("kind")
            if kind == "artifact-update":
                print(f"  artifact  {result['artifact'].get('name')}")
            elif kind == "status-update":
                print(f"  status    {result['status']['state']}")
            else:
                print(f"  {kind}")

        print()
        print(f"=== 共收到 {events} 个事件 ===")


if __name__ == "__main__":
    main()
