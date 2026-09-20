"""What the scoring agent does with one validated request (plan step 5.5).

Kept tiny on purpose: the actual scoring lives in ``backend.app.services.scoring_agent``
(unit-tested on the host); this module just runs it off the event loop, since it opens a blocking
database session.
"""

from __future__ import annotations

import asyncio
import os

from agent_base.runner import AgentResult

from backend.app.services.scoring_agent import ScoringRequest, score_from_database

AGENT_NAME = "sitescout-scoring"
AGENT_VERSION = "0.1.0"


async def handle(request: ScoringRequest) -> AgentResult:
    """Score the request against the database named by ``DATABASE_URL``."""
    database_url = os.environ["DATABASE_URL"]
    payload = await asyncio.to_thread(score_from_database, database_url, request)
    return AgentResult(payload=payload)
