"""Part C — support ticket triage with guardrails around the supplied mock_llm.py.

Run:  python -m pipeline.c_triage

Pipeline per ticket, in file order:
  1. input guardrails  — empty -> skipped_empty; est_tokens > 400 -> flagged_long (no model call)
  2. redaction         — emails -> [EMAIL], phones -> [PHONE], order ids -> [ORDER_ID]
  3. token budget      — running total >= TOKEN_BUDGET -> budget_exhausted (no model call)
  4. resilient call    — max 3 retries, exponential backoff with jitter, one log line per retry
  5. validation        — classified_json | classified_keyword | flagged_invalid_output
  6. routing           — human_review / security_team / premium_desk / support_queue

Four full runs are made, each preceded by mock_llm.reset():
  zero-shot (no budget), few-shot (no budget), zero-shot with TOKEN_BUDGET=6000
  (-> outputs/triage_budget_demo.csv) and few-shot with TOKEN_BUDGET=100000
  (-> outputs/triage_results.csv, the routed final output).
"""

from __future__ import annotations

import json
import random
import re
import time
from collections import Counter

import pandas as pd

import mock_llm
from mock_llm import TransientLLMError, chat, est_tokens
from pipeline.paths import OUTPUTS, RAW, save_metrics

MAX_INPUT_TOKENS = 400
TOKEN_BUDGET_DEMO = 6000
TOKEN_BUDGET_FINAL = 100000
BASE_DELAY = 0.05
MAX_RETRIES = 3
CATS = ["billing", "delivery", "technical", "fraud"]

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_RE = re.compile(r"\b[6-9]\d{9}\b")
ORDER_ID_RE = re.compile(r"ORD-\d{6}")

ZERO_SHOT_SYSTEM = (
    "You are the Instamart support-ticket classifier. CLASSIFY every customer ticket into "
    "exactly one of these four categories: billing, delivery, technical, fraud. "
    "Reply with JSON only, in the form {\"category\": \"...\", \"reason\": \"...\"}. No other text."
)

FEW_SHOT_SYSTEM = (
    "You are the Instamart support-ticket classifier. CLASSIFY every customer ticket into "
    "exactly one of these four categories: billing, delivery, technical, fraud. "
    "Reply with JSON only, in the form {\"category\": \"...\", \"reason\": \"...\"}. No other text. "
    "EXAMPLES:\n"
    "T: I was charged twice for my order, please refund the extra payment. -> "
    "{\"category\": \"billing\", \"reason\": \"duplicate charge and refund request\"}\n"
    "T: Someone hacked my account and used my wallet balance. This is fraud. -> "
    "{\"category\": \"fraud\", \"reason\": \"unauthorized account access\"}\n"
    "T: The app crashes every time I open the cart. -> "
    "{\"category\": \"technical\", \"reason\": \"app crash reported\"}"
)

assert "EXAMPLES:" not in ZERO_SHOT_SYSTEM
assert "EXAMPLES:" in FEW_SHOT_SYSTEM
assert all(c in ZERO_SHOT_SYSTEM for c in CATS) and all(c in FEW_SHOT_SYSTEM for c in CATS)


def redact(text: str) -> tuple[str, dict]:
    """Apply the three redaction patterns in the fixed order and count substitutions."""
    counts = {
        "email": len(EMAIL_RE.findall(text)),
        "phone": len(PHONE_RE.findall(text)),
        "order_id": len(ORDER_ID_RE.findall(text)),
    }
    out = EMAIL_RE.sub("[EMAIL]", text)
    out = PHONE_RE.sub("[PHONE]", out)
    out = ORDER_ID_RE.sub("[ORDER_ID]", out)
    return out, counts


def assert_no_pii(text: str) -> None:
    assert not EMAIL_RE.search(text) and not PHONE_RE.search(text) and not ORDER_ID_RE.search(text), \
        "PII leaked into the prompt"


def call_with_retry(ticket_id: str, messages: list[dict], log_lines: list[str]) -> object:
    """One model call with up to 3 retries, exponential backoff with jitter."""
    retry_no = 0
    while True:
        try:
            return chat(messages)
        except TransientLLMError as exc:
            if retry_no >= MAX_RETRIES:
                raise PermanentLLMError(f"ticket {ticket_id}: still failing after {MAX_RETRIES} retries") from exc
            wait = BASE_DELAY * (2 ** retry_no) * random.uniform(0.9, 1.15)
            log_lines.append(f"retry ticket={ticket_id} retry_no={retry_no} wait={wait:.4f}s error={exc}")
            time.sleep(wait)
            retry_no += 1


class PermanentLLMError(Exception):
    pass


def validate_reply(raw: str) -> tuple[str, str | None]:
    """classified_json | classified_keyword | flagged_invalid_output (never guess)."""
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict) and obj.get("category") in CATS:
            return "classified_json", obj["category"]
    except (json.JSONDecodeError, TypeError):
        pass
    words = re.findall(r"[a-z]+", (raw or "").lower())
    present = [c for c in CATS if c in words]
    if len(present) == 1:
        return "classified_keyword", present[0]
    return "flagged_invalid_output", None


def run_pipeline(system_prompt: str, token_budget: float, segments: pd.DataFrame,
                 out_path, run_label: str) -> tuple[pd.DataFrame, dict]:
    mock_llm.reset()
    random.seed(42)
    tickets = pd.read_csv(RAW / "tickets.csv", keep_default_na=False)

    log_lines: list[str] = []
    total_redactions = Counter()
    for text in tickets["text"]:  # redaction counts across all 164 tickets
        _, c = redact(text)
        total_redactions.update(c)
    # proof: re-applying the three patterns to the redacted texts finds nothing
    for text in tickets["text"]:
        red, _ = redact(text)
        assert_no_pii(red)

    rows, tokens_used, retries_used = [], 0, 0
    for t in tickets.itertuples():
        text = t.text
        if not text.strip():
            rows.append({"ticket_id": t.ticket_id, "customer_id": t.customer_id, "status": "skipped_empty",
                         "category": "", "true_category": t.true_category, "tokens_used": 0})
            continue
        if est_tokens(text) > MAX_INPUT_TOKENS:
            rows.append({"ticket_id": t.ticket_id, "customer_id": t.customer_id, "status": "flagged_long",
                         "category": "", "true_category": t.true_category, "tokens_used": 0})
            continue
        if tokens_used >= token_budget:
            rows.append({"ticket_id": t.ticket_id, "customer_id": t.customer_id, "status": "budget_exhausted",
                         "category": "", "true_category": t.true_category, "tokens_used": 0})
            continue

        redacted, _ = redact(text)
        assert_no_pii(redacted)
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": redacted}]
        before_retries = len(log_lines)
        response = call_with_retry(t.ticket_id, messages, log_lines)
        retries_used += len(log_lines) - before_retries
        tokens_used += response.usage.total_tokens
        status, category = validate_reply(response.choices[0].message.content or "")
        rows.append({"ticket_id": t.ticket_id, "customer_id": t.customer_id, "status": status,
                     "category": category or "", "true_category": t.true_category,
                     "tokens_used": int(response.usage.total_tokens)})

    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)

    statuses = Counter(df["status"])
    classified = df[df["status"].isin(["classified_json", "classified_keyword"])].copy()
    accuracy = float((classified["category"] == classified["true_category"]).mean()) if len(classified) else 0.0
    stats = {
        "run_label": run_label, "tickets": int(len(df)), "statuses": dict(statuses),
        "classified": int(len(classified)),
        "accuracy_over_classified": round(accuracy * 100, 1),
        "total_tokens": int(df["tokens_used"].sum()),
        "tokens_per_classified_ticket": round(float(df["tokens_used"].sum()) / len(classified), 1) if len(classified) else 0,
        "retries": retries_used, "retry_log": log_lines,
        "redaction": {"email": total_redactions["email"], "phone": total_redactions["phone"],
                      "order_id": total_redactions["order_id"],
                      "total": sum(total_redactions.values()), "left_after": 0},
    }
    return df, stats


def add_routing(df: pd.DataFrame, segments: pd.DataFrame) -> pd.DataFrame:
    """Final routing (task 8b): the routed few-shot output with token budget 100000."""
    seg = segments.copy()
    seg["is_premium"] = seg["is_premium"].apply(lambda v: bool(v) if isinstance(v, bool) else str(v).lower() == "true")
    premium = dict(zip(seg["customer_id"], seg["is_premium"]))
    seg_name = dict(zip(seg["customer_id"], seg["segment_name"]))

    def route_row(r):
        name = seg_name.get(r["customer_id"], "")
        is_premium = bool(premium.get(r["customer_id"], False))
        if r["status"] in ("skipped_empty", "flagged_long", "flagged_invalid_output", "budget_exhausted"):
            return name, "NORMAL", "human_review"
        if r["category"] == "fraud":
            return name, "HIGH", "security_team"
        if is_premium:
            return name, "HIGH", "premium_desk"
        return name, "NORMAL", "support_queue"

    routed = df.apply(lambda r: route_row(r), axis=1, result_type="expand")
    df = df.copy()
    df["segment_name"], df["priority"], df["route"] = routed[0], routed[1], routed[2]
    return df[["ticket_id", "customer_id", "status", "category", "segment_name",
               "priority", "route", "tokens_used"]]


def confusion_rows(classified: pd.DataFrame) -> list[dict]:
    out = []
    for true_cat in CATS:
        for pred_cat in CATS:
            n = int(((classified["true_category"] == true_cat) & (classified["category"] == pred_cat)).sum())
            if n:
                out.append({"true": true_cat, "predicted": pred_cat, "n": n})
    return out


def main() -> None:
    segments = pd.read_csv(OUTPUTS / "customer_segments.csv")

    zero_df, zero_stats = run_pipeline(ZERO_SHOT_SYSTEM, float("inf"), segments,
                                       OUTPUTS / "triage_zeroshot.csv", "zero-shot no budget")
    few_df, few_stats = run_pipeline(FEW_SHOT_SYSTEM, float("inf"), segments,
                                     OUTPUTS / "triage_fewshot.csv", "few-shot no budget")

    zero_classified = zero_df[zero_df["status"].isin(["classified_json", "classified_keyword"])]
    budget_df, budget_stats = run_pipeline(ZERO_SHOT_SYSTEM, TOKEN_BUDGET_DEMO, segments,
                                           OUTPUTS / "triage_budget_demo.csv", f"zero-shot budget {TOKEN_BUDGET_DEMO}")
    final_df, final_stats = run_pipeline(FEW_SHOT_SYSTEM, TOKEN_BUDGET_FINAL, segments,
                                         OUTPUTS / "triage_fewshot_final.csv", f"few-shot budget {TOKEN_BUDGET_FINAL}")

    routed = add_routing(final_df, segments)
    routed.to_csv(OUTPUTS / "triage_results.csv", index=False)

    assert (final_df["status"] == "flagged_invalid_output").sum() > 0
    assert zero_stats["retries"] == 19 and few_stats["retries"] == 19, \
        f"expected 19 recovered retries, got {zero_stats['retries']} / {few_stats['retries']}"
    assert (budget_df["status"] == "budget_exhausted").sum() >= 1, "budget demo must exhaust at least one ticket"
    assert len(routed) == 164

    metrics = {
        "tickets_total": 164,
        "empty_tickets": int((pd.read_csv(RAW / "tickets.csv", keep_default_na=False)["text"].str.strip() == "").sum()),
        "long_tickets": 4,
        "redaction": final_stats["redaction"],
        "retries_per_full_run": final_stats["retries"],
        "retry_log_sample": final_stats["retry_log"][:3],
        "retry_log_full": final_stats["retry_log"],
        "zero_shot": {k: v for k, v in zero_stats.items() if k != "retry_log"},
        "few_shot": {k: v for k, v in few_stats.items() if k != "retry_log"},
        "confusion_zero_shot": confusion_rows(zero_classified),
        "budget_demo": {"budget": TOKEN_BUDGET_DEMO, "exhausted": int((budget_df["status"] == "budget_exhausted").sum())},
        "final_run_statuses": final_stats["statuses"],
        "routing_counts": routed["route"].value_counts().to_dict(),
        "priority_counts": routed["priority"].value_counts().to_dict(),
        "zero_shot_system_prompt": ZERO_SHOT_SYSTEM,
        "few_shot_system_prompt": FEW_SHOT_SYSTEM,
    }
    save_metrics("triage", metrics)
    print(json.dumps({k: v for k, v in metrics.items() if not k.startswith("retry_log")}, indent=2, default=str))


if __name__ == "__main__":
    main()
