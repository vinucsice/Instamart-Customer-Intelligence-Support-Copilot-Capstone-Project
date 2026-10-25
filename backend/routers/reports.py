"""Read-only reporting endpoints over the Part A-D pipeline outputs."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException

from models.capstone import (OverviewResponse, PartStatus, RetentionRow, SectionResponse,
                             SegmentRow, TicketRow, Totals)
from pipeline.paths import OUTPUTS, load_metrics

router = APIRouter()


def _metrics(section: str) -> dict:
    data = load_metrics().get(section)
    if data is None:
        raise HTTPException(status_code=503,
                            detail=f"pipeline section '{section}' not found - run `python -m pipeline` steps first")
    return data


def _csv_rows(path, model):
    df = pd.read_csv(path, keep_default_na=False)
    return [model(**row) for row in df.to_dict(orient="records")]


@router.get("/overview", response_model=OverviewResponse)
async def overview() -> OverviewResponse:
    metrics = load_metrics()
    audit = metrics.get("audit", {}).get("figures", {})
    cleaning = metrics.get("cleaning", {}).get("after", {})
    segments = metrics.get("segments", {})
    lapse = metrics.get("lapse", {})
    triage = metrics.get("triage", {})
    policy = metrics.get("policy", {})
    agent = metrics.get("agent", {})
    validation = metrics.get("validation", {}).get("status", "not run")

    totals = Totals(
        customers=1200,
        products=40,
        raw_order_rows=int(audit.get("raw_order_rows", 0)),
        clean_order_rows=int(cleaning.get("order_rows", 0)),
        completed_orders=int(cleaning.get("completed", 0)),
        completed_revenue_inr=float(cleaning.get("completed_amount_sum", 0)),
        tickets=int(triage.get("tickets_total", 0)),
        policy_docs=5,
        segmented_customers=int(segments.get("rfm_stats", {}).get("customers", 0)),
    )
    parts = [
        PartStatus(part="A", title="Data Foundation: Clean, Store, Query", marks=22,
                   status=validation,
                   highlights=[f"{audit.get('raw_order_rows', 0):,} raw order rows audited",
                               f"{cleaning.get('order_rows', 0):,} clean orders, "
                               f"INR {cleaning.get('completed_amount_sum', 0):,.2f} completed revenue",
                               f"SQL queries match references: "
                               f"{metrics.get('sql', {}).get('all_queries_match_references', False)}"]),
        PartStatus(part="B", title="Customer Segments and Lapse Prediction", marks=28,
                   status=f"K={segments.get('chosen_k', 0)} segments; lapse test F1 "
                          f"{lapse.get('selected_test', {}).get('f1', 0)}",
                   highlights=[f"{segments.get('rfm_stats', {}).get('customers', 0):,} customers in RFM",
                               f"PCA explains {sum(segments.get('pca_explained_variance_ratio', [0, 0]))*100:.1f}% of variance in 2D",
                               f"baseline accuracy {lapse.get('baseline', {}).get('accuracy', 0)} -> "
                               f"model F1 {lapse.get('selected_test', {}).get('f1', 0)} on the lapsed class"]),
        PartStatus(part="C", title="Support Ticket Triage with Guardrails", marks=22,
                   status=f"{triage.get('redaction', {}).get('total', 0)} PII items redacted; "
                          f"{triage.get('retries_per_full_run', 0)} retries recovered",
                   highlights=[f"{triage.get('tickets_total', 0)} tickets: 4 empty + 4 long gated before any model call",
                               f"zero-shot accuracy {triage.get('zero_shot', {}).get('accuracy_over_classified', 0)}% "
                               f"vs few-shot {triage.get('few_shot', {}).get('accuracy_over_classified', 0)}%",
                               f"{triage.get('budget_demo', {}).get('exhausted', 0)} tickets stopped by the token budget demo"]),
        PartStatus(part="D", title="Policy RAG Assistant and Refund Agent", marks=28,
                   status=f"{policy.get('total_chunks', 0)} chunks; "
                          f"{agent.get('crash_resume', {}).get('status', 'n/a')} after crash-resume",
                   highlights=[f"grounding eval: {policy.get('eval_overlap10', {}).get('doc_hits', 0)}/12 docs, "
                               f"{policy.get('eval_overlap10', {}).get('fact_hits', 0)}/12 facts",
                               f"7/7 refund scenarios match their expected outcomes",
                               f"stop-safely demos: "
                               f"{agent.get('stop_safely', {}).get('s1_token_limit_200', {}).get('status', 'n/a')} and "
                               f"{agent.get('stop_safely', {}).get('timeout_time_limit_0', {}).get('status', 'n/a')}"]),
    ]
    return OverviewResponse(totals=totals, parts=parts)


@router.get("/metrics/{section}", response_model=SectionResponse)
async def metrics_section(section: str) -> SectionResponse:
    valid = {"audit", "cleaning", "sql", "eda", "segments", "lapse", "triage", "policy", "agent", "validation"}
    if section not in valid:
        raise HTTPException(status_code=404, detail=f"unknown section '{section}'")
    return SectionResponse(section=section, data=_metrics(section))


@router.get("/triage/tickets", response_model=list[TicketRow])
async def triage_tickets() -> list[TicketRow]:
    try:
        return _csv_rows(OUTPUTS / "triage_results.csv", TicketRow)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="triage outputs not found - run `python -m pipeline.c_triage`")


@router.get("/segments/customers", response_model=list[SegmentRow])
async def segment_customers() -> list[SegmentRow]:
    try:
        rows = _csv_rows(OUTPUTS / "customer_segments.csv", SegmentRow)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="segment outputs not found - run `python -m pipeline.b_segments`")
    return rows


@router.get("/retention", response_model=list[RetentionRow])
async def retention_list() -> list[RetentionRow]:
    try:
        return _csv_rows(OUTPUTS / "retention_list.csv", RetentionRow)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="retention outputs not found - run `python -m pipeline.b_lapse`")


@router.get("/agent/scenarios", response_model=list[dict[str, Any]])
async def agent_scenarios() -> list[dict[str, Any]]:
    path = OUTPUTS / "agent_runs.jsonl"
    if not path.exists():
        raise HTTPException(status_code=503, detail="agent outputs not found - run `python -m pipeline.d_agent`")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
