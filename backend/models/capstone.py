"""Pydantic v2 models for the Copilot API.

Every model here has a hand-written TS mirror in frontend/src/lib/types.ts — when you change
one, change the other in the same edit.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ overview
class Totals(BaseModel):
    customers: int
    products: int
    raw_order_rows: int
    clean_order_rows: int
    completed_orders: int
    completed_revenue_inr: float
    tickets: int
    policy_docs: int
    segmented_customers: int


class PartStatus(BaseModel):
    part: str
    title: str
    marks: int
    status: str
    highlights: list[str]


class OverviewResponse(BaseModel):
    totals: Totals
    parts: list[PartStatus]


# ------------------------------------------------------------------ metrics passthrough
class SectionResponse(BaseModel):
    section: str
    data: dict[str, Any]


# ------------------------------------------------------------------ part C tickets
class TicketRow(BaseModel):
    ticket_id: str
    customer_id: str
    status: str
    category: str
    segment_name: str
    priority: str
    route: str
    tokens_used: int


# ------------------------------------------------------------------ part B segments
class SegmentRow(BaseModel):
    customer_id: str
    recency: int
    frequency: int
    monetary: float
    segment_id: int
    segment_name: str
    is_premium: bool


class RetentionRow(BaseModel):
    customer_id: str
    lapse_probability: float
    actually_lapsed: int


# ------------------------------------------------------------------ part D copilot
class PolicyAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class PolicySource(BaseModel):
    source: str
    score: float
    text: str


class PolicyAskResponse(BaseModel):
    answer: str
    sources: list[PolicySource]


class AgentRunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class AgentStep(BaseModel):
    step: int
    tool: str
    arguments: dict[str, Any]
    observation: Any = None


class AgentRunResponse(BaseModel):
    run_id: str
    scenario_id: str
    status: str
    final_answer: str
    steps: list[AgentStep]
    llm_calls: int
    tokens_used: int
    tools_executed: list[str]
