# Instamart Customer Intelligence & Support Copilot

## What it is
The complete 100-mark capstone delivered as one repository: a reproducible Python pipeline (Parts A–D) that turns dirty Instamart exports into a trusted database, segments customers, predicts lapsing customers, triages support tickets with guardrails, and runs a policy Q&A assistant plus a refund agent — every graded number matching the brief's reference checkpoints. On top of it, a working web Copilot UI that puts those results in front of a business user.

## Who it's for
The Head of Customer Experience and the retention / support-desk teams who need one trusted internal tool instead of raw exports, spreadsheets and guesswork — and the course grader who clones the repo and re-runs the README commands.

## Core features and experience
- **Data Foundation (Part A)** — audit and clean the raw exports with documented rules (duplicates, pending leftovers, impossible values, messy cities/genders/ages), store clean tables in SQLite, seven SQL analyses, pandas cross-checks, and a validation script that prints ALL CHECKPOINTS PASSED.
- **Segments & lapse prediction (Part B)** — RFM table, K-means segmentation with named segments (Premium flag), PCA projection, a leakage-safe lapse model that beats the baseline, class-balance experiment, interpretable model saved and reloaded, and a Premium retention watch-list.
- **Ticket triage with guardrails (Part C)** — empty/long-ticket gates, PII redaction (email/phone/order id) before any model call, zero-shot vs few-shot comparison, resilient retried calls, strict output validation with human-review fallback, token budgeting, and final routing (security team / premium desk / support queue / human review) that uses Part B's segments.
- **Policy assistant & refund agent (Part D)** — TF-IDF retrieval over the five policy documents with grounding evaluation, a five-tool refund agent (order lookup from the SQLite DB, policy search, refund calculation, issue/escalate) run over all seven scenarios with iteration/token/time stop-safely limits, a crash-and-resume demonstration, and JSONL ledgers.
- **Web Copilot UI** — a single internal-tool app with views for each part: data-quality and cleaning summary, segment explorer with the retention list, a triage console over the 164 tickets (statuses, routes, PII redaction proof, token spend), and a policy assistant you can ask questions plus a refund-agent runner showing each tool step. All numbers in the UI come from the real pipeline outputs — nothing mocked. No API keys, no network: all model calls go through the supplied offline `mock_llm.py`, exactly as the brief requires.
- **The graded artifact** — repo on branch `main` with the two supplied files unmodified, committed outputs, `sql/queries.sql`, `requirements.txt`, `.gitignore`, and one `README.md` with the required sections: Overview, Reproduce (numbered commands), Part A–D (every reported number as a table/list, the seven-scenario result table, the two stop-safely demo statuses, the crash-and-resume tool list), Limitations and Next Steps (including the Premium-flag post-hoc caveat). All money in INR, never a dollar sign. Git initialised locally with commits on `main`, ready to push.

## Phase 1: what gets built now
Everything, in dependency order, in one pass:
1. Repo scaffolding on `main` — supplied files unmodified, `.gitignore`, requirements, data generation and raw audit (Part A tasks 1–2).
2. Cleaning, SQLite storage, validation checkpoints, `sql/queries.sql`, pandas cross-checks (Part A tasks 3–6).
3. RFM, K-means, named segments, PCA, leakage-safe lapse model, class-balance experiment, persistence and retention list (Part B).
4. Triage pipeline with all guardrails, both prompts, retries, validation, budget demo and final routing output (Part C).
5. Policy retrieval, grounding evaluation incl. the zero-overlap failure, five tools, ReAct loop over all seven scenarios, stop-safely demos, crash-and-resume, JSONL outputs (Part D).
6. The web Copilot UI over these results, wired through the backend API.
7. README with every reported number, tier-1 verification (API smoke, typecheck, one browser pass through the core journey), then final commit on `main`.

Decisions already taken from your answers: full capstone + web UI, all four parts end-to-end, designer's choice on the look, git initialised and committed on `main`. Remaining judgement calls (final K for clustering from {3,4,5}, which tuned model ships) are decided by the brief's own criteria — elbow/silhouette/interpretability and test F1 — and documented in the README.