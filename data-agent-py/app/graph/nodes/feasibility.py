"""可行性评估节点。

真实现要做的（阶段 3）：
  把"改写后的问题 + 召回的表结构 + 证据 + 多轮上下文"交给 LLM，
  让它判断这个需求属于什么类型，输出一段带标记的文本。

【注意】下一个节点是条件边，它靠字符串匹配决定往哪走：
  结果里包含"【需求类型】：《数据分析》" → 继续
  否则 → 直接结束
所以这个空壳必须把那个标记带上，否则图会立刻结束、看不到后面的节点。
"""

from app.graph.state import AgentState, StateKey


async def feasibility_node(state: AgentState) -> dict:
    query = state.get(StateKey.REWRITE_QUERY, "")
    print(f"  [FEASIBILITY] 判断可行性：{query!r}")

    return {
        StateKey.FEASIBILITY_RESULT: (
            "【需求类型】：《数据分析》\n"
            "【可行性】：可行\n"
            "【理由】：[假] 阶段 3 由 LLM 给出"
        )
    }
