"""SiteScout scoring A2A agent (plan step 5.5): ranks stored zones for a category and tier."""

from __future__ import annotations

import logging
import os

import click
import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from agent_base.a2a_glue import JsonAgentExecutor
from agent_base.runner import run_json_agent
from agent_handler import AGENT_NAME, AGENT_VERSION, handle
from starlette.applications import Starlette

from backend.app.services.scoring_agent import ScoringRequest

logging.basicConfig(level=logging.INFO)


def build_app(host: str, port: int) -> Starlette:
    """The A2A application: agent card routes plus the JSON-RPC endpoint at ``/``."""
    skill = AgentSkill(
        id="rank_zones",
        name="Rank store locations",
        description=(
            "Given a city, category, tier, questionnaire answers and constraints, returns the "
            "best zones ranked by score with explanations."
        ),
        tags=["scoring", "site-selection", "ranking", "retail"],
        examples=['{"city": "bengaluru", "category": "cafe", "tier": "mid", "top_n": 5}'],
    )
    card = AgentCard(
        name=AGENT_NAME,
        description=(
            "Ranks candidate store locations (H3 cells) for a category and tier from "
            "pre-computed area features stored in the SiteScout database (read only)."
        ),
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC", url=os.getenv("HOST_OVERRIDE", f"http://{host}:{port}/")
            )
        ],
        version=AGENT_VERSION,
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )

    async def runner(message_text: str | None) -> dict[str, object]:
        return await run_json_agent(
            agent=AGENT_NAME,
            version=AGENT_VERSION,
            input_model=ScoringRequest,
            handler=handle,
            message_text=message_text,
        )

    handler = DefaultRequestHandler(
        agent_executor=JsonAgentExecutor(runner), task_store=InMemoryTaskStore(), agent_card=card
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
