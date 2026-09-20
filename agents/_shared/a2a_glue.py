"""A2A glue: turns ``run_json_agent`` into an executor for the A2A SDK.

This file needs ``a2a-sdk`` (installed inside each agent container), so it is exercised by the
agent smoke test after deployment rather than by the host unit tests. All logic worth testing
lives in ``runner.py``.

Replies are sent as ONE text artifact holding the JSON envelope, which every A2A client can read.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

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

Runner = Callable[[str | None], Awaitable[dict[str, Any]]]


class JsonAgentExecutor(AgentExecutor):
    """Feeds the user's text to ``runner`` and returns its envelope as JSON text."""

    def __init__(self, runner: Runner) -> None:
        self._runner = runner

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task or new_task_from_user_message(context.message)
        await event_queue.enqueue_event(task)
        await event_queue.enqueue_event(self._status(task, TaskState.TASK_STATE_WORKING))

        reply = await self._runner(context.get_user_input())
        state = TaskState.TASK_STATE_FAILED if "error" in reply else TaskState.TASK_STATE_COMPLETED
        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=task.id,
                context_id=task.context_id,
                artifact=Artifact(
                    artifact_id=str(uuid.uuid4()),
                    parts=[Part(text=json.dumps(reply, ensure_ascii=False))],
                ),
                append=False,
                last_chunk=True,
            )
        )
        await event_queue.enqueue_event(self._status(task, state))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Agents are short-lived request handlers; there is nothing to cancel."""

    @staticmethod
    def _status(task: Any, state: TaskState) -> TaskStatusUpdateEvent:
        return TaskStatusUpdateEvent(
            task_id=task.id, context_id=task.context_id, status=TaskStatus(state=state)
        )
