# data-agent-py

data-agent 的 Python 重写版。当前处于 **阶段 0：A2A 协议骨架** ——
只搭了对外通信层，业务内容是假的。

## 现在能干什么

- `GET /.well-known/agent-card.json` —— 返回 Agent 名片
- `POST /a2a/jsonrpc` —— 接收 JSON-RPC 请求，支持 `message/stream` 流式
- 收到消息后，按真实图的节点顺序发一串 `[假数据]` 产物给前端

## 跑起来

前置：Python 3.11 或 3.12（不要用 3.13+）。

```bash
cd data-agent-py
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -e .
python -m app.main
```

看到 `Uvicorn running on http://0.0.0.0:9933` 就是起来了。

## 验证

```bash
# 1) 名片
curl http://localhost:9933/.well-known/agent-card.json

# 2) 流式请求（-N 关掉缓冲，否则看不到流）
curl -N -X POST http://localhost:9933/a2a/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/stream",
       "params":{"message":{"messageId":"m1","role":"user","kind":"message",
       "metadata":{"databaseId":"california_schools"},
       "parts":[{"kind":"text","text":"有多少学校？"}]}}}'
```

3) 打开前端页面发个问题，应该能看到一串 `[假数据]` 卡片依次出现。
   看到卡片 = A2A 协议层全线打通。

## 注意

- **端口 9933 和 Java 版冲突**：跑这个就别同时开 Java 版后端。
- **前端一行都不用改**：名片里的 URL 指向 Vite 代理（3500），
  和 Java 版名片写法一致，代理会自动转发到 9933。
- 如果 `pip install -e .` 之后启动报 ImportError，试试
  `pip install "a2a-sdk[http-server]"`。
- A2A SDK 的导入路径各版本偶有微调，报 ImportError 就把报错贴出来对一下。

## 下一步

| 阶段 | 内容 |
| --- | --- |
| 1 | 数据层：PG + pgvector + BIRD 数据导入 + 检索函数 |
| 2 | 图骨架：LangGraph，13 个节点先填空壳 |
| 3 | 逐个节点填业务逻辑（先 SQL 主链路，后 Python 分析链路） |
| 4 | 人工审核闭环（中断 / 恢复） |

对照的 Java 源码在隔壁 `../data-agent-backend/`。
