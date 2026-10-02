"""A2A 执行器：收到消息后干什么。

这是整个 A2A 层唯一有业务逻辑的地方，对应 Java 版的 GraphAgentExecutor。
**阶段 0 里它是假的**：不发真结果，只按真实图的节点顺序发一串占位产物，
目的是把「协议格式」这条路走通。

等阶段 2 接上图之后，这里面的 for 循环会被换成真正的
`async for chunk in graph.astream(...)`，其余结构不变。
"""

import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, Task, TaskState, TaskStatus
from a2a.utils.errors import UnsupportedOperationError

from app.graph.node_names import END_ARTIFACT_NAME, GraphNode

logger = logging.getLogger(__name__)


# 前端靠 metadata.outputType 区分卡片是「进行中」还是「已完成」：
#   GRAPH_NODE_STREAMING → 进行中（卡片会持续追加内容）
#   GRAPH_NODE_FINISHED  → 已完成
# 这两个取值不能改，前端 WorkspacePage.vue 里写死了。
OUTPUT_STREAMING = "GRAPH_NODE_STREAMING"
OUTPUT_FINISHED = "GRAPH_NODE_FINISHED"


# 假装跑一遍流水线，顺序照抄真实图的走向
FAKE_FLOW = [
    GraphNode.EVIDENCE_RECALL,
    GraphNode.SCHEMA_RECALL,
    GraphNode.TABLE_RELATION,
    GraphNode.FEASIBILITY_ASSESSMENT,
    GraphNode.PLANNER,
    GraphNode.HUMAN_FEEDBACK,
    GraphNode.SUPERVISOR,
    GraphNode.SQL_GENERATION,
    GraphNode.SQL_EXECUTION,
    GraphNode.REPORT_GENERATION,
]


class GraphAgentExecutor(AgentExecutor):

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

        # ---- 2) 取输入 ----
        #取的是用户问题和元数据
        # 真实现里这两样东西后面要交给图当初始 state
        user_input = context.get_user_input()
        metadata = context.metadata or {}
        logger.info(
            "收到请求 input=%r databaseId=%r task_id=%s",
            user_input,
            metadata.get("databaseId"),
            context.task_id,
        )

        # ---- 3) 按节点顺序往外发产物 ----
        for node_name in FAKE_FLOW:
            # 第一个节点演示「流式分片 + 收尾」两段式：
            # 中间几次发 STREAMING（前端显示进行中），最后发 FINISHED 收尾。
            # 真实现里 LLM 逐字输出就对应这一段。
            if node_name == GraphNode.EVIDENCE_RECALL:
                for chunk in ("[假数据] 正在改写问题…", "[假数据] 正在检索术语…"):
                    await updater.add_artifact(
                        parts=[Part(text=chunk)],
                        name=node_name,
                        metadata={"outputType": OUTPUT_STREAMING},
                    )

            await updater.add_artifact(
                #向前端推送一个“产物/消息”。
                parts=[
                    Part(text=f"[假数据] {node_name} 跑完了。收到的输入是：{user_input}")
                ],
                name=node_name,
                metadata={"outputType": OUTPUT_FINISHED},
            )

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
