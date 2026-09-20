"""A2A executor: read the user's text, ask the LLM, return one text artifact."""

from __future__ import annotations

import logging
import uuid

from a2a.helpers import new_task_from_user_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    Artifact,
    Part,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from llm import LlmError, ask

logger = logging.getLogger(__name__)


class HelloExecutor(AgentExecutor):
    """Answers each message with one LLM reply; failures are returned as readable text."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        question = context.get_user_input()
        task = context.current_task or new_task_from_user_message(context.message)
        await event_queue.enqueue_event(task)
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task.id,
                context_id=task.context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_WORKING),
            )
        )

        try:
            answer = await ask(question)
            final_state = TaskState.TASK_STATE_COMPLETED
        except LlmError as exc:
            logger.error("llm call failed: %s", exc)
            answer = f"LLM call failed: {exc}"
            final_state = TaskState.TASK_STATE_FAILED

        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=task.id,
                context_id=task.context_id,
                artifact=Artifact(artifact_id=str(uuid.uuid4()), parts=[Part(text=answer)]),
                append=False,
                last_chunk=True,
            )
        )
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task.id,
                context_id=task.context_id,
                status=TaskStatus(state=final_state),
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Nothing long-running to cancel."""
