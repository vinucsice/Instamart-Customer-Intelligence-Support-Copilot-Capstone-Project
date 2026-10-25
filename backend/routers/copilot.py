"""Live Copilot endpoints: the grounded policy assistant and the refund agent runner.

Both run the REAL Part D pipeline code against mock_llm.py — the same offline model the
graded pipeline uses. Live runs keep the graded artifacts untouched: their ledger lines go
to outputs/live_refund_ledger.jsonl and their checkpoints to state/live-*.json.
"""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, HTTPException

import pipeline.d_agent as d_agent
import pipeline.d_policy as d_policy
from models.capstone import (AgentRunRequest, AgentRunResponse, PolicyAskRequest,
                             PolicyAskResponse, PolicySource)

router = APIRouter()


@router.post("/policy/ask", response_model=PolicyAskResponse)
async def policy_ask(payload: PolicyAskRequest) -> PolicyAskResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question must not be empty")
    answer_text, _ = await asyncio.to_thread(d_policy.answer, question)
    chunks = await asyncio.to_thread(d_policy.retrieve, question, 3)
    return PolicyAskResponse(answer=answer_text, sources=[PolicySource(**c) for c in chunks])


@router.post("/agent/run", response_model=AgentRunResponse)
async def agent_run(payload: AgentRunRequest) -> AgentRunResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="message must not be empty")
    run_id = f"live-{uuid.uuid4().hex[:12]}"
    canonical = d_agent.LEDGER_PATH
    try:
        d_agent.LEDGER_PATH = d_agent.LIVE_LEDGER_PATH
        result = await asyncio.to_thread(
            d_agent.run_agent, message, "UI", 6, 6000, 10.0, run_id, None)
    finally:
        d_agent.LEDGER_PATH = canonical
    return AgentRunResponse(**result)
