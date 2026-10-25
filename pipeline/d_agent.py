"""Part D, tasks 5-8 — the five refund tools, the ReAct loop with stop-safely limits,
checkpointed runs and resume.

Run:  python -m pipeline.d_agent

Runs all 7 rows of data/raw/agent_scenarios.csv into outputs/agent_runs.jsonl, the issued and
escalated actions into outputs/refund_ledger.jsonl, checkpoints into state/, the two
stop-safely demonstrations and the crash-and-resume demonstration.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone

import pandas as pd

import mock_llm
from pipeline.d_policy import retrieve
from pipeline.paths import DB_PATH, OUTPUTS, RAW, STATE, save_metrics

AGENT_SYSTEM = ("You are the Instamart refund AGENT. Resolve the customer's refund request by "
                "calling tools: get_order, search_policy, calculate_refund, then issue_refund or "
                "escalate_to_human. Finish with one line starting REFUND:, ESCALATE:, DENIED: or NOT_FOUND:.")

LEDGER_PATH = OUTPUTS / "refund_ledger.jsonl"
LIVE_LEDGER_PATH = OUTPUTS / "live_refund_ledger.jsonl"

TOOLS_SPEC = [
    {"name": "get_order",
     "description": "Look up one order by id in the clean Instamart database.",
     "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}},
    {"name": "search_policy",
     "description": "Search the policy documents with TF-IDF retrieval and return the top chunks.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "calculate_refund",
     "description": "Apply the refund rules to an order amount and delivery time.",
     "parameters": {"type": "object", "properties": {"order_amount": {"type": "number"},
                                                     "delivery_minutes": {"type": "number"}},
                    "required": ["order_amount", "delivery_minutes"]}},
    {"name": "issue_refund",
     "description": "Issue the refund and record it in the refund ledger.",
     "parameters": {"type": "object", "properties": {"order_id": {"type": "string"},
                                                     "refund_inr": {"type": "number"}},
                    "required": ["order_id", "refund_inr"]}},
    {"name": "escalate_to_human",
     "description": "Send a refund above INR 1000 to a human support lead and record it.",
     "parameters": {"type": "object", "properties": {"order_id": {"type": "string"},
                                                     "refund_inr": {"type": "number"}},
                    "required": ["order_id", "refund_inr"]}},
]


# --------------------------------------------------------------------------- tools
def get_order(order_id: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT order_id, status, order_amount, delivery_minutes FROM orders "
                           "WHERE order_id = ?", (order_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return {"error": "order not found"}
    return {"order_id": row[0], "status": row[1], "order_amount": row[2], "delivery_minutes": row[3]}


def search_policy(query: str) -> dict:
    return {"results": retrieve(query, k=3)}


def calculate_refund(order_amount: float, delivery_minutes: float | None) -> dict:
    """Refund rules: delivered in more than 45 minutes -> 100% of the amount; 45 or less -> 0."""
    if delivery_minutes is not None and float(delivery_minutes) > 45:
        return {"refund_inr": round(float(order_amount), 2)}
    return {"refund_inr": 0.0}


def _ledger(tool: str, order_id: str, refund_inr: float) -> None:
    line = {"timestamp": datetime.now(timezone.utc).isoformat(), "tool": tool,
            "order_id": order_id, "refund_inr": refund_inr}
    with open(LEDGER_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


def issue_refund(order_id: str, refund_inr: float) -> dict:
    _ledger("issue_refund", order_id, refund_inr)
    return {"refund_inr": round(float(refund_inr), 2)}


def escalate_to_human(order_id: str, refund_inr: float) -> dict:
    _ledger("escalate_to_human", order_id, refund_inr)
    return {"refund_inr": round(float(refund_inr), 2)}


TOOL_MAP = {"get_order": get_order, "search_policy": search_policy, "calculate_refund": calculate_refund,
            "issue_refund": issue_refund, "escalate_to_human": escalate_to_human}


# --------------------------------------------------------------------------- loop
class SimulatedCrash(Exception):
    """Raised by the crash-and-resume demonstration."""


def _checkpoint_path(run_id: str):
    return STATE / f"{run_id}.json"


def _save_checkpoint(state: dict) -> None:
    _checkpoint_path(state["run_id"]).write_text(json.dumps({
        "run_id": state["run_id"], "scenario_id": state["scenario_id"],
        "messages": state["messages"], "tokens_used": state["tokens_used"],
        "llm_calls": state["llm_calls"], "step_number": len(state["steps"]),
        "tools_executed": state["tools_executed"], "steps": state["steps"],
    }, indent=2), encoding="utf-8")


def _continue(state: dict, max_iterations: int, token_limit: int, time_limit_seconds: float,
              crash_after_step: int | None = None) -> dict:
    """The ReAct loop; `state` carries messages, tokens_used, llm_calls, steps, tools_executed."""
    start = time.monotonic()
    status = final_answer = None
    for _ in range(max_iterations):
        if time.monotonic() - start >= time_limit_seconds:
            status = "FALLBACK_TIMEOUT"
            final_answer = ("HANDOFF: the run stopped before resolving the request — wall-clock time limit of "
                            f"{time_limit_seconds}s reached. A human agent must continue from step "
                            f"{len(state['steps']) + 1}.")
            break
        response = mock_llm.chat(state["messages"])
        state["llm_calls"] += 1
        state["tokens_used"] += response.usage.total_tokens
        if state["tokens_used"] > token_limit:
            status = "FALLBACK_TOKEN_LIMIT"
            final_answer = (f"HANDOFF: token budget of {token_limit} exceeded after {state['llm_calls']} model calls "
                            f"without a resolution — the requested tool was not executed. A human lead must take over.")
            break
        message = response.choices[0].message
        if not message.tool_calls:
            final_answer = message.content
            status = final_answer.split(":", 1)[0].strip() if ":" in (final_answer or "") else "DONE"
            break
        call = {"id": message.tool_calls[0].id, "name": message.tool_calls[0].name,
                "arguments": dict(message.tool_calls[0].arguments)}
        state["messages"].append({"role": "assistant", "content": None, "tool_calls": [call]})
        observation = TOOL_MAP[call["name"]](**call["arguments"])
        state["steps"].append({"step": len(state["steps"]) + 1, "tool": call["name"],
                               "arguments": call["arguments"], "observation": observation})
        state["tools_executed"].append(call["name"])
        state["messages"].append({"role": "tool", "tool_call_id": call["id"], "name": call["name"],
                                  "content": json.dumps(observation)})
        _save_checkpoint(state)
        if crash_after_step is not None and len(state["steps"]) == crash_after_step:
            raise SimulatedCrash(f"simulated crash after tool execution {len(state['steps'])}")
    else:
        status = "FALLBACK_MAX_ITERATIONS"
        final_answer = (f"HANDOFF: no final answer within {max_iterations} model calls — handing the case to a human "
                        f"agent. Tools executed so far: {', '.join(state['tools_executed']) or 'none'}.")
    return {"run_id": state["run_id"], "scenario_id": state["scenario_id"], "status": status,
            "final_answer": final_answer, "steps": state["steps"], "llm_calls": state["llm_calls"],
            "tokens_used": int(state["tokens_used"]), "tools_executed": state["tools_executed"]}


def run_agent(user_message: str, scenario_id: str, max_iterations: int = 6, token_limit: int = 6000,
              time_limit_seconds: float = 10.0, run_id: str | None = None,
              crash_after_step: int | None = None) -> dict:
    state = {"run_id": run_id or f"{scenario_id}-{uuid.uuid4().hex[:8]}", "scenario_id": scenario_id,
             "messages": [{"role": "system", "content": AGENT_SYSTEM}, {"role": "user", "content": user_message}],
             "tokens_used": 0, "llm_calls": 0, "steps": [], "tools_executed": []}
    return _continue(state, max_iterations, token_limit, time_limit_seconds, crash_after_step)


def resume_agent(run_id: str, max_iterations: int = 6, token_limit: int = 6000,
                 time_limit_seconds: float = 10.0) -> dict:
    """Load a checkpoint from state/ and continue the run."""
    saved = json.loads(_checkpoint_path(run_id).read_text(encoding="utf-8"))
    state = {"run_id": saved["run_id"], "scenario_id": saved["scenario_id"], "messages": saved["messages"],
             "tokens_used": saved["tokens_used"], "llm_calls": saved["llm_calls"], "steps": saved["steps"],
             "tools_executed": saved["tools_executed"]}
    return _continue(state, max_iterations, token_limit, time_limit_seconds)


# --------------------------------------------------------------------------- main
def _extract_refund(result: dict) -> float:
    for step in result["steps"]:
        if step["tool"] in ("issue_refund", "escalate_to_human"):
            return float(step["observation"]["refund_inr"])
    return 0.0


def main() -> None:
    scenarios = pd.read_csv(RAW / "agent_scenarios.csv", keep_default_na=False)

    # ---- task 6: the 7 canonical scenario runs ---------------------------------------
    runs = []
    # a fresh ledger per script run keeps this step idempotent: exactly the canonical lines
    open(OUTPUTS / "refund_ledger.jsonl", "w", encoding="utf-8").close()
    with open(OUTPUTS / "agent_runs.jsonl", "w", encoding="utf-8") as f:
        for s in scenarios.itertuples():
            result = run_agent(s.message, s.scenario_id, run_id=f"scenario-{s.scenario_id}")
            runs.append(result)
            f.write(json.dumps({"scenario_id": result["scenario_id"], "status": result["status"],
                                "final_answer": result["final_answer"], "llm_calls": result["llm_calls"],
                                "tokens_used": result["tokens_used"], "steps": result["steps"]}) + "\n")

    # ---- task 7: stop-safely demonstrations (kept off the canonical ledger) ----------
    global LEDGER_PATH
    canonical_ledger = LEDGER_PATH
    try:
        LEDGER_PATH = LIVE_LEDGER_PATH
        token_demo = run_agent(scenarios.loc[0, "message"], "S1-token-limit-demo",
                               token_limit=200, run_id="demo-token-limit-S1")
        timeout_demo = run_agent(scenarios.loc[0, "message"], "S1-timeout-demo",
                                 time_limit_seconds=0, run_id="demo-timeout-S1")
        # ---- task 8: crash-and-resume demonstration ----------------------------------
        crash_run_id = "demo-crash-resume-S1"
        try:
            run_agent(scenarios.loc[0, "message"], "S1-crash-resume", run_id=crash_run_id, crash_after_step=2)
            raise AssertionError("the simulated crash did not fire")
        except SimulatedCrash:
            pass
        resumed = resume_agent(crash_run_id)
    finally:
        LEDGER_PATH = canonical_ledger

    assert token_demo["status"] == "FALLBACK_TOKEN_LIMIT", token_demo["status"]
    assert timeout_demo["status"] == "FALLBACK_TIMEOUT", timeout_demo["status"]
    assert resumed["tools_executed"] == ["get_order", "search_policy", "calculate_refund", "issue_refund"], \
        resumed["tools_executed"]
    assert resumed["status"] == "REFUND" and abs(_extract_refund(resumed) - 128.25) < 0.01

    # ---- task 6 checks: every scenario matches its expected outcome -------------------
    for s, result in zip(scenarios.itertuples(), runs):
        expected_amount = float(s.expected_refund_inr)
        assert result["status"].startswith(s.expected_outcome), \
            f"{s.scenario_id}: {result['status']} != {s.expected_outcome}"
        assert abs(_extract_refund(result) - expected_amount) < 0.01, s.scenario_id
    assert runs[0]["llm_calls"] == 5, runs[0]["llm_calls"]

    react_comparison = (
        "ReAct spends one model call per decision: measured on our runs, S1 took 5 calls (get_order, "
        "search_policy, calculate_refund, issue_refund, final answer), the cancelled-order case S5 took 3 and "
        "the unknown-order case S6 took 2, at a few hundred to a few thousand estimated tokens each. A "
        "plan-and-execute design would ask the model for the whole step list once and replan only on error: the "
        "happy path needs about 2 calls instead of 5, but an unexpected observation such as NOT_FOUND or a "
        "cancelled order invalidates the remaining planned steps and forces a replanning round trip anyway, so "
        "the saving shrinks exactly where it matters. Because each tool's arguments here depend on the previous "
        "observation (the order id, then the retrieved policy, then the calculated amount), ReAct reacts to "
        "reality at every hop with no wasted plans. I would keep ReAct for this refund workflow: the sequences "
        "are short and strictly ordered, its extra calls are bounded by the max-iteration, token and time "
        "stop-safely limits, and a one-shot plan cannot anticipate which branch the order data will justify."
    )

    metrics = {
        "scenarios": [{"scenario_id": r["scenario_id"], "status": r["status"], "final_answer": r["final_answer"],
                       "llm_calls": r["llm_calls"], "tokens_used": r["tokens_used"],
                       "tools": r["tools_executed"], "refund_inr": _extract_refund(r),
                       "message": s.message} for s, r in zip(scenarios.itertuples(), runs)],
        "expected_all_matched": True,
        "stop_safely": {
            "s1_token_limit_200": {"status": token_demo["status"], "llm_calls": token_demo["llm_calls"],
                                   "tokens_used": token_demo["tokens_used"]},
            "timeout_time_limit_0": {"status": timeout_demo["status"], "llm_calls": timeout_demo["llm_calls"]},
        },
        "crash_resume": {"run_id": resumed["run_id"], "status": resumed["status"],
                         "final_answer": resumed["final_answer"],
                         "tools_in_order": resumed["tools_executed"], "refund_inr": _extract_refund(resumed)},
        "react_comparison": react_comparison,
        "react_comparison_words": len(react_comparison.split()),
        "tools_spec": TOOLS_SPEC,
    }
    assert metrics["react_comparison_words"] <= 250
    save_metrics("agent", metrics)
    print(f"7 scenarios OK; demos: {token_demo['status']}, {timeout_demo['status']}; "
          f"crash-resume tools: {' -> '.join(resumed['tools_executed'])}")


if __name__ == "__main__":
    main()
