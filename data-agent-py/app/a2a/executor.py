"""A2A 执行器：收到消息后干什么。

这是整个 A2A 层唯一有业务逻辑的地方，对应 Java 版的 GraphAgentExecutor。

【阶段 2 的变化】
  之前：一个写死的 for 循环，按顺序发假产物。
  现在：真跑 LangGraph 的图，把每个节点的输出转发出去。

  节点的内部逻辑目前还是假的（阶段 3 才填），但**图的执行是真的**——
  分支、循环、状态传递全都在真跑。
"""

import json
import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, Task, TaskState, TaskStatus
from a2a.utils.errors import UnsupportedOperationError

from app.graph.builder import compile_graph
from app.graph.node_names import END_ARTIFACT_NAME
from app.graph.state import StateKey

logger = logging.getLogger(__name__)


# 前端靠 metadata.outputType 区分卡片是「进行中」还是「已完成」：
#   GRAPH_NODE_STREAMING → 进行中（卡片会持续追加内容）
#   GRAPH_NODE_FINISHED  → 已完成
# 这两个取值不能改，前端 WorkspacePage.vue 里写死了。
OUTPUT_STREAMING = "GRAPH_NODE_STREAMING"
OUTPUT_FINISHED = "GRAPH_NODE_FINISHED"


class GraphAgentExecutor(AgentExecutor):

    def __init__(self) -> None:
        # 图编译一次就够，不用每个请求都编。
        # 阶段 5 加检查点后这里要改成带 checkpointer 的编译。
        self.graph = compile_graph()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # ---- 1 新任务：先建 Task 并塞进事件队列 ----
        # 这个版本的框架规定：执行器必须先把 Task 事件放进队列，
        # 之后才允许发状态更新和产物，否则队列直接报错拒绝。
        # 人工审核后的续跑不会走这里（current_task 已经有值了）。
        if context.current_task is None:
            await event_queue.enqueue_event(
                Task(
                    id=context.task_id,
                    context_id=context.context_id,
                    status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
                    history=[context.message],
                )
            )

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.submit()      # 告诉客户端：收到了
        await updater.start_work()  # 告诉客户端：开始干了

        # ---- 2) 组装图的初始状态 ----
        user_input = context.get_user_input()
        metadata = context.metadata or {}
        database_id = metadata.get("databaseId", "")
        logger.info(
            "收到请求 input=%r databaseId=%r task_id=%s",
            user_input,
            database_id,
            context.task_id,
        )

        initial_state = {
            StateKey.USER_INPUT: user_input,
            StateKey.DATABASE_ID: database_id,
        }

        # ---- 3) 跑图，每跑完一个节点就往外发一条产物 ----
        # stream_mode="updates" 的返回形状：{节点名: 这个节点写入的字段}
        try:
            async for chunk in self.graph.astream(initial_state, stream_mode="updates"):
                for node_name, update in chunk.items():
                    await updater.add_artifact(
                        parts=[Part(text=_summarize(update))],
                        name=node_name,
                        metadata={"outputType": OUTPUT_FINISHED},
                    )
        except Exception:
            # 图里任何一个节点抛异常，都要让客户端知道（否则前端会一直转圈）
            logger.exception("图执行失败")
            await updater.fail()
            return

        # ---- 4) 发结束信号 ----
        # 前端认这个约定：收到 name == "__END__" 的产物就把所有卡片收尾。
        await updater.add_artifact(
            parts=[Part(text="")],
            name=END_ARTIFACT_NAME,
        )
        await updater.complete()

        # 阶段 4 要在这里加人工审核：
        #   跑到 HUMAN_FEEDBACK 前停下 → await updater.requires_input()
        #   用户回传后带着同一个 task_id 再进来 → 从检查点续跑

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Java 版这里也是空实现，阶段 0 先照旧
        logger.warning("cancel 尚未实现")
        raise UnsupportedOperationError()


def _summarize(update: dict | None) -> str:
    """把节点写回状态的内容压成一段可读文本，作为卡片上显示的内容。

    阶段 3 各节点会有自己的展示格式，那时候这个方法基本就用不上了。
    """
    if not update:
        return "（无输出）"
    lines = []
    for key, value in update.items():
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        if len(text) > 200:
            text = text[:200] + "…"
        lines.append(f"{key}: {text}")
    return "\n".join(lines)
