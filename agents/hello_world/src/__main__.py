"""SiteScout hello-world A2A agent (Nasiko phase 0.3 feasibility test)."""

from __future__ import annotations

import logging
import os

import click
import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from agent_executor import HelloExecutor
from starlette.applications import Starlette

logging.basicConfig(level=logging.INFO)


def build_app(host: str, port: int) -> Starlette:
    """The A2A application: agent card routes plus the JSON-RPC endpoint at ``/``."""
    skill = AgentSkill(
        id="hello",
        name="Answer a short question",
        description="Answers a short general question in one or two sentences.",
        tags=["test", "hello"],
        examples=["What makes a good location for a pharmacy?"],
    )
    card = AgentCard(
        name="sitescout-hello",
        description="Minimal SiteScout test agent that answers through the platform LLM router.",
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC", url=os.getenv("HOST_OVERRIDE", f"http://{host}:{port}/")
            )
        ],
        version="0.1.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )
    handler = DefaultRequestHandler(
        agent_executor=HelloExecutor(), task_store=InMemoryTaskStore(), agent_card=card
    )
    routes = [*create_agent_card_routes(card), *create_jsonrpc_routes(handler, rpc_url="/")]
    return Starlette(routes=routes)


@click.command()
@click.option("--host", default="localhost")
@click.option("--port", default=8000)
def main(host: str, port: int) -> None:
    """Start the agent server."""
    uvicorn.run(build_app(host, port), host=host, port=port)


if __name__ == "__main__":
    main()
