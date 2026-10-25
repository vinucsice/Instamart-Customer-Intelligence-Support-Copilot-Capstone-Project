# Instamart Customer Intelligence & Support Copilot

## Overview

One internal tool, four connected parts, built on synthetic (fictional, seeded) Instamart data:

| Part | What it does |
|---|---|
| A | Audits the dirty raw exports, cleans them with documented rules, stores `customers` / `products` / `orders` in SQLite + CSV, answers seven business questions in SQL and cross-checks them in pandas 
| B | Builds the RFM table, K-means segments (named, with a Premium flag), and a leakage-safe lapse-prediction model plus a Premium retention watch-list
| C | Triages the 164 support tickets behind input guardrails, PII redaction, retries, strict output validation and a token budget, then routes them using the Part B segments
| D | Grounds a policy Q&A assistant in TF-IDF retrieval over the five policy documents and runs a five-tool refund agent (order lookup, policy search, refund calculation, issue/escalate) over seven scenarios with stop-safely limits, checkpoints and resume 

Everything runs offline: every language-model call goes through the supplied `mock_llm.py` (unmodified) — no API key, no network, no cost. All money is in Indian Rupees (INR); no dollar sign appears anywhere in this repository.

**The web Copilot app.** This repository also ships a web UI for the Head of Customer Experience and the support desk (FastAPI in `backend/`, React 19 + TypeScript in `frontend/`). It renders the real pipeline outputs — raw audit figures, cleaning-rule counts, SQL results, segment explorer with the retention list, lapse model card, the routed ticket ledger with filters, a live grounded policy Q&A and a live refund-agent runner with the tool timeline. It reads the committed pipeline outputs (plus `live_refund_ledger.jsonl` for live agent runs, so the graded artifacts stay untouched); no feature is mocked. Running it is optional for grading:

```shell
cd backend && uvicorn server:app --host 0.0.0.0 --port 8001   # serves /api, reads outputs/
cd frontend && yarn install && yarn dev                        # serves the UI on :3000, proxies /api
```

Each part consumes what the previous parts produced (B reads `data/clean/`, C reads B's segment file, D's agent reads `data/instamart.db` and reuses D's retrieval), which is why the pipeline is run strictly in the order below.

## Reproduce

From a clean clone, with Python 3.11+:

1. `python -m venv .venv`
2. `source .venv/bin/activate`  (Windows: `.venv\Scripts\activate`)
3. `pip install -r requirements.txt`
4. `python generate_data.py`  — last line prints `generated: customers=1200 products=40 orders_raw=13084 tickets=164`
5. `python -m pipeline.a_audit`  — audits the raw exports (writes the audit section of `outputs/metrics.json`)
6. `python -m pipeline.a_clean`  — cleans customers + orders, writes `data/clean/*.csv` and `data/instamart.db`
7. `python -m pipeline.a_validate`  — asserts the Part A checkpoints, prints `ALL CHECKPOINTS PASSED`
8. `python -m pipeline.a_sql`  — runs the seven queries from `sql/queries.sql` against the database
9. `python -m pipeline.a_eda`  — pandas cross-checks and the exploratory analysis
10. `python -m pipeline.b_segments`  — RFM, K-means table, named segments, PCA, `outputs/customer_segments.csv`
11. `python -m pipeline.b_lapse`  — lapse features, grid searches, class-balance experiment, `outputs/lapse_model.joblib`, `outputs/retention_list.csv`
12. `python -m pipeline.c_triage`  — the four triage runs, `outputs/triage_results.csv`, `outputs/triage_budget_demo.csv`
13. `python -m pipeline.d_policy`  — chunking, retrieval, grounding evaluation (overlap 10 and 0)
14. `python -m pipeline.d_agent`  — the seven agent scenarios, stop-safely demos, crash-and-resume, `outputs/agent_runs.jsonl`, `outputs/refund_ledger.jsonl`, `state/`

Every script is deterministic (seeds fixed as specified below) and idempotent — re-running any step reproduces the same bytes and the same numbers.

## Part A

### Audit of the raw data (task 2)

Per-table shapes and per-column missing counts are reported by `pipeline.a_audit` (also stored in `outputs/metrics.json` → `audit`). The specific audit figures:

| Audit figure | Value |
|---|---|
| raw `orders.csv` rows | 13,084 |
| exact duplicate rows | 119 |
| rows with status `pending` | 656 |
| distinct `order_id` | 12,309 |
| `order_amount` entries that cannot be converted to a number | 120 |
| negative `delivery_minutes` | 106 |
| blank `delivery_minutes` | 2,541 |
| customers: blank `age` | 61 |
| customers: `age` outside 10–100 | 6 |
| customers: distinct raw city spellings | 24 |
| customers: distinct non-blank raw gender spellings | 10 |
| customers: blank `gender` | 30 |

### Customer cleaning (task 3)

| Rule | Values changed |
|---|---|
| city: strip spaces + title case → exactly six cities | 476 |
| gender: every spelling mapped to `male`/`female`/`unknown` (blank → unknown) | 495 |
| ages outside 10–100 set to missing, then all missing ages filled with the city median (`groupby` + `transform`) | 67 filled, of which 6 out-of-range |
| `signup_date` converted to datetime | 1,200 |

Result: Pune 227, Delhi 210, Bengaluru 197, Chennai 191, Hyderabad 191, Mumbai 184; genders female 610, male 560, unknown 30; 0 missing ages, every age between 18 and 60.

### Order cleaning (task 4, applied strictly in this order)

| Step | Rule | Rows/values changed |
|---|---|---|
| 1 | `order_ts` converted to datetime | 13,084 |
| 2 | exact duplicate rows removed | 119 |
| 3 | per `order_id`, keep only the record with the latest `order_ts` (drops the earlier `pending` records) | 656 |
| 4 | `order_amount` to numeric (unparseable → missing), then filled as `round(price_inr x quantity x (1 - discount_pct/100), 2)` from the product price | 112 imputed |
| 5 | negative `delivery_minutes` set to missing | 105 |
| 6 | completed orders: missing `delivery_minutes` filled with the product-category median among completed orders | 774 |
| 7 | cancelled orders: `delivery_minutes` left missing (never delivered — imputing would invent data) | 1,199 left missing |

Result: 12,309 rows (one per order); 11,110 completed, 1,199 cancelled, 0 pending; 0 missing `order_amount`; 0 missing `delivery_minutes` among completed, 1,199 among cancelled; sum of `order_amount` over completed orders = **INR 2,998,668.80**.

### Store and validate (task 5)

The three clean tables are written to `data/clean/*.csv` and to the SQLite database `data/instamart.db` (tables `customers`, `products`, `orders`; `order_ts` stored as text `YYYY-MM-DD HH:MM:SS`). `python -m pipeline.a_validate` asserts 28 checkpoints (rows, statuses, missingness, the revenue sum, city/gender counts, every raw audit figure, the three tables present) and prints **ALL CHECKPOINTS PASSED**.

### SQL analysis (task 6)

Seven queries in `sql/queries.sql`, each executed with `pd.read_sql_query` by `pipeline.a_sql`:

| Query | Result |
|---|---|
| Q1 — `WHERE` then `HAVING`: customers whose completed orders above INR 500 total more than INR 8000 | 30 customers |
| Q2 — three-table join: revenue by city and category | 30 rows; total INR 2,998,668.80; largest cell Bengaluru / Electronics = INR 2,33,909.45 |
| Q3 — scalar subquery: products above the average catalogue price | 11 products |
| Q4 — `LEFT JOIN`: customers with no completed order | 25 customers |
| Q5 — CTE: per-customer completed spend vs the average of those totals | 550 customers above; average INR 2,552.06 |
| Q6 — window functions: `RANK()` / `DENSE_RANK()` / `ROW_NUMBER()` per city by total spend | top per city: Bengaluru C0082 (INR 12,856.20), Chennai C0930 (INR 10,151.40), Delhi C0291 (INR 13,742.60), Hyderabad C0743 (INR 12,730.05), Mumbai C0693 (INR 14,766.55), Pune C0426 (INR 10,377.10); exactly **8 rows** have `RANK()` different from `ROW_NUMBER()` — tied total spends share a RANK while ROW_NUMBER still counts each row, so ties make them diverge |
| Q7 — running total: daily completed revenue with `SUM(...) OVER (ORDER BY day)` | 183 daily rows; last cumulative value INR 2,998,668.80 |

### Pandas cross-check and exploratory analysis (task 7)

- `pd.pivot_table(..., margins=True)` on the Q2 shape has grand total INR 2,998,668.80 — identical to the SQL total (asserted). Named aggregation per city: Bengaluru sum INR 5,23,643.40, mean INR 276.47, count 1,894; Mumbai sum INR 4,79,058.50, mean INR 297.00, count 1,613.
- Distribution of completed `order_amount`: mean INR 269.91 vs median INR 135.00 (right-skewed), skewness 4.61, Q1 INR 64.80, Q3 INR 297.00, IQR INR 232.20; 1.5×IQR fences at INR -283.50 and INR 645.30 → **897 outliers above** the upper fence, 0 below.
- Correlations over completed orders (`order_amount`, `discount_pct`, `quantity`, `delivery_minutes`): the largest in absolute value is `order_amount` with `discount_pct` at about **−0.095** (`order_amount` with `quantity` is +0.087, slightly smaller).

Written answers (152 words, also rendered by `pipeline.a_eda`):

> **What is this data about?** Completed Instamart orders in six metro cities from April to September 2025: 11,110 orders by 1,175 customers over a 40-product catalogue, each row holding amount, discount, quantity and delivery minutes. **What do the distributions look like?** Amounts average INR 269.91 but the median is only INR 135.00 and skewness is about 4.61 — a long right tail of a few large electronics baskets. **Are there outliers or anomalies?** Yes: the 1.5×IQR fences (Q1 64.80, Q3 297.00) put 897 orders above the upper fence of 645.30 and none below the lower fence; they are genuine big-basket orders, not data errors. **What relationships exist?** All correlations are weak: the largest in absolute value is order_amount with discount_pct at about −0.095 (order_amount with quantity is +0.087, slightly smaller). Bigger discounts pair with slightly bigger orders, but a correlation this small explains almost no variance — it does not establish causation.

## Part B

### RFM table (task 1)

Snapshot 2025-10-01 00:00:00, completed orders only: **1,175 customers**; recency median 19 days (min 0, max 180); frequency mean 9.46 (max 33); monetary mean INR 2,552.06 (max INR 14,766.55).

### K-means (task 2)

`KMeans(n_clusters=K, n_init=10, random_state=42)` on `StandardScaler`-transformed RFM:

| K | inertia | silhouette |
|---|---|---|
| 2 | 1,820.8 | 0.465 |
| 3 | 1,268.2 | 0.445 |
| 4 | 743.1 | **0.526** |
| 5 | 617.4 | 0.481 |
| 6 | 503.2 | 0.482 |
| 7 | 408.5 | 0.416 |
| 8 | 366.5 | 0.412 |

**Chosen K = 4** (from {3, 4, 5}): the highest silhouette in the range and a four-way split the business can act on (protect / reward / win back / nudge). Why K=8's lower inertia cannot pick K: inertia always falls as K grows because more centroids cut the squared distances (it would reach 0 at K = n), so a lower value alone rewards overfitting; the elbow, the silhouette and business interpretability pick K. Cluster numbers are only labels with no ordering.

### Segments (task 3)

| Segment id | Name | Size | Mean recency | Mean frequency | Mean monetary | Recommended action |
|---|---|---|---|---|---|---|
| 1 | **Premium** (flagged) | 138 | 24.1 d | 6.8 | INR 7,129.70 | Protect: priority support, early access, loyalty perks |
| 2 | Loyal Regulars | 419 | 8.8 d | 19.4 | INR 3,410.02 | Reward and upsell: bundles, subscriptions, referral nudges |
| 0 | At-Risk High Value | 436 | 28.9 d | 3.8 | INR 1,057.62 | Win back within 7 days: personal offers and follow-up calls |
| 3 | Occasional Shoppers | 182 | 109.0 d | 2.2 | INR 685.99 | Nudge with coupons and reminders to rebuild the habit |

`PCA(n_components=2)` on the scaled RFM matrix: explained variance **0.634 + 0.218 = 0.852**. Written to `outputs/customer_segments.csv` (`customer_id, recency, frequency, monetary, segment_id, segment_name, is_premium`).

### Lapse problem (task 4)

Cutoff 2025-09-01; features use only orders strictly before the cutoff plus the clean customer table. Cohort **1,156** customers; **443 lapsed (38.32%)**; split 924 train / 232 test (`test_size=0.2, stratify=y, random_state=42`). Baseline (always "not lapsed"): accuracy **61.6%**, lapsed-class F1 **0** (`zero_division=0`). Features: recency, frequency, monetary, mean `discount_pct`, cancellation rate, mean `delivery_minutes`, favourite category, city, age, gender, tenure. No order dated on or after the cutoff and no task-3 segment label entered the features (asserted in code).

### Preprocessing without leakage (task 5)

`OneHotEncoder(drop="first")` (city, gender, favourite category) + `StandardScaler` (numeric) inside a `Pipeline`/`ColumnTransformer` **fitted on the 924 training rows only** and merely applied to the test rows. The fitted scaler's learned mean of frequency is **8.115** vs the full-cohort mean **8.029** — they differ because the scaler is fitted on the training split only, so it learned the training rows' mean, not the whole cohort's. No feature column contains a missing value (asserted).

### Train, tune, evaluate (task 6)

- Logistic regression — grid `C ∈ {0.01, 0.1, 1, 10, 100}`, cv=5, scoring f1: best **C = 100**, best cv F1 **0.651**; test P 0.644 / R 0.652 / **F1 0.648**.
- Random forest — grid `max_depth ∈ {3, 5, 8}` x `min_samples_leaf ∈ {5, 10, 20}` (45 fits), cv=5, scoring f1: best **depth 8, leaf 10**, best cv F1 **0.681**; test P 0.659 / R 0.652 / **F1 0.655**.
- Confusion matrices on the untouched test set: logistic [[111, 32], [31, 58]]; random forest [[113, 30], [31, 58]].
- **Selected: random forest.** Missing a lapsing customer costs the whole future revenue of someone who could have been saved, while wrongly targeting a loyal customer costs one cheap coupon — at equal F1 the forest's slightly better precision on the lapsed class wastes fewer goodwill offers, and it keeps the recall at 0.652. Its test F1 (0.655) clears the 0.55 bar. (The brief's reference split chose C = 1; our feature build reproduces the same order of results — cv F1 0.651, test F1 0.648 for the regression.)

### Class-balance experiment (task 6)

Training set oversampled (duplicates of lapsed rows with replacement, `random_state=42`) to 570/570; the best logistic regression refit on it and scored on the unchanged test set:

| LR on | precision | recall | F1 |
|---|---|---|---|
| original train | 0.644 | 0.652 | 0.648 |
| balanced train | 0.589 | **0.854** | 0.697 |

**Recall moved most** (+20.2 points while precision dipped 5.5): the retention team catches far more lapsing customers for a modest rise in wasted targets.

### Interpret, persist, use (task 7)

Top-5 random-forest importances: frequency 0.280 (more orders, less lapse), monetary 0.271, recency 0.115 (staler customers lapse more), avg delivery minutes 0.061 (slow deliveries nudge customers away), cancel rate 0.052 (bad experiences predict lapse). Logistic-regression coefficient signs: recency **+** (staler → more likely to lapse), frequency **−** (habitual customers stay), monetary **+** (bigger but sparser baskets slightly raise lapse odds once frequency is controlled).

`outputs/lapse_model.joblib` saved with `joblib.dump`, reloaded with `joblib.load` — the reloaded model reproduces the original test predictions exactly (asserted). The Premium test customers ranked by predicted lapse probability, top 10, are in `outputs/retention_list.csv` (`customer_id, lapse_probability, actually_lapsed`); **1 of the 10 truly lapsed**. The Premium flag comes from the whole-window RFM of task 3, which includes the September window that defines the lapse label, so the retention list is illustrative and not a leakage-free evaluation; the model's own features still use only orders before the cutoff.

## Part C

### Guardrails and redaction (tasks 1–2)

- 4 empty tickets → `skipped_empty`, 4 long tickets (`est_tokens` = 734 > `MAX_INPUT_TOKENS = 400`) → `flagged_long`; none ever reaches the model.
- Redaction, in order — email → `[EMAIL]` (55), phone → `[PHONE]` (91), order id → `[ORDER_ID]` (132): **278 substitutions in total; re-applying the three patterns to the redacted texts finds 0 leftovers** (asserted in code). The user message sent to the model is exactly the redacted ticket text and nothing else (also asserted).

### Resilience, validation, prompts (tasks 3–4)

- `mock_llm.reset()` before each full run; every model call is wrapped in a retry with a maximum of 3 retries and exponential backoff with jitter (`BASE_DELAY = 0.05` s; wait = 0.05 x 2^n x U(0.9, 1.15) — every retry in these runs is retry 0, waits 0.045–0.0575 s, one log line per retry). A full run produces exactly **19 TransientLLMErrors, all recovered**; no ticket ends in a permanent error.
- Output validation over the 156 eligible tickets: **135 `classified_json`, 12 `classified_keyword`, 9 `flagged_invalid_output`** (routed to human review, never guessed). The keyword path extracts words with `re.findall(r"[a-z]+", text.lower())`, so "billing-related" yields `billing`.

### Zero-shot vs few-shot (task 5)

| Run | Classified | Accuracy | Total tokens | Tokens / classified ticket |
|---|---|---|---|---|
| zero-shot | 147 | **85.7%** (126/147) | 11,584 | 78.8 |
| few-shot | 147 | **100%** | 23,752 | 161.6 |

Zero-shot confusion (147): billing 38/38, delivery 36/36, technical 29/39 (10 → billing), fraud 23/34 (11 → billing). The few-shot prompt costs 82.8 extra tokens per ticket and buys +14.3 accuracy points: every zero-shot error is a fraud or technical ticket whose plain words ("charged", "payment") also exist in billing, and the two labelled examples — including the fraud one — teach the priority that fixes it; at 100% accuracy there is nothing left to buy, so the extra tokens are worth paying whenever a mis-routed fraud ticket is costlier than ~83 tokens of compute.

### Budget, routing, output (task 6)

- Token-budget demo: zero-shot with `TOKEN_BUDGET = 6000` → **75 tickets** ended `budget_exhausted` (routed to human review without a model call) → `outputs/triage_budget_demo.csv`.
- Final output `outputs/triage_results.csv` (164 rows) from a few-shot run with `TOKEN_BUDGET = 100000`: columns `ticket_id, customer_id, status, category, segment_name, priority, route, tokens_used`. Routing (segment file from Part B; unknown customers treated as not premium): skipped/long/invalid/budget → `human_review` / NORMAL (17); fraud → `security_team` / HIGH (34); premium → `premium_desk` / HIGH (11); else `support_queue` / NORMAL (102).

## Part D

### Chunks, retrieval, answers, evaluation (tasks 1–4)

- 40-word chunks with 10-word overlap → **15 chunks**: refund 4, delivery 3, escalation 3, payment 3, privacy 2.
- `TfidfVectorizer()` fitted on the chunk texts; `retrieve(query, k=3)` ranks by `cosine_similarity` and returns `{source, score, text}`. For "refund policy late delivery" the top three chunks all come from `refund_policy.txt`. TF measures how often a word occurs inside a chunk; IDF down-weights words that occur across many chunks, so policy-specific terms drive the similarity. Limitation: TF-IDF is purely lexical, so two phrasings with the same meaning but different words ("money back" vs "refund") never match.
- `answer(question)`: retrieve 3 chunks → a `POLICY ASSISTANT` system message (answer only from context, admit when it cannot be found) + a user message of exactly `CONTEXT:` / three `[{source}] {text}` lines / `QUESTION:` / the question.
- Grounding evaluation (`data/raw/policy_eval.csv`): expected doc in the top-3 sources **12/12**; expected fact in the answer **12/12**; unanswerable questions getting the "I could not find…" fallback **2/2**.
- Zero-overlap run (40-word chunks, overlap 0): **2 of the 12 answerable questions break** — "What delivery time makes a completed order eligible for a full refund?" (fact "more than 45 minutes") and "How soon is money returned when a payment fails but is deducted?" (fact "48 hours") — because the sentence that holds each fact straddles a chunk boundary, so no retrieved chunk contains the complete sentence.

### Tools and the agent loop (tasks 5–6)

Five tools in `TOOLS_SPEC` + `TOOL_MAP`: `get_order` (reads `data/instamart.db`; returns order fields or `{"error": "order not found"}`), `search_policy` (the retrieval above), `calculate_refund` (refund rules: only completed orders; delivered > 45 min → 100% of the amount; ≤ 45 min → 0), `issue_refund` and `escalate_to_human` (each appends a timestamped JSON line to `outputs/refund_ledger.jsonl`). The ReAct loop (`run_agent`) calls `mock_llm.chat`, executes requested tools, appends tool messages and returns `{status, final_answer, steps, llm_calls, tokens_used}`.

The seven scenarios (all match their expected outcomes; refund amounts within 0.01):

| Scenario | Status | Refund | Model calls | Tokens |
|---|---|---|---|---|
| S1 | REFUND | INR 128.25 | 5 | 1,037 |
| S2 | REFUND | INR 135.00 | 5 | 1,037 |
| S3 | ESCALATE | INR 1,999.00 | 5 | 1,024 |
| S4 | DENIED | — | 4 | 717 |
| S5 | DENIED | — | 3 | 421 |
| S6 | NOT_FOUND | — | 2 | 128 |
| S7 | FALLBACK_MAX_ITERATIONS | — | 6 | 3,168 |

### Stop safely and resume (tasks 7–8)

- S1 with `token_limit=200` → **FALLBACK_TOKEN_LIMIT** (3 model calls, 438 tokens; the tool requested by the last call was not executed). The default `token_limit=6000` never stops S7 early (3,168 tokens over its six calls).
- `time_limit_seconds=0` → **FALLBACK_TIMEOUT** before the first model call (0 model calls).
- S7 (`[LOOP]`) spins on `search_policy` until the 6-iteration cap → **FALLBACK_MAX_ITERATIONS** with a human-handoff summary.
- Crash-and-resume: a simulated crash right after the second tool execution (its checkpoint already saved in `state/`), then `resume_agent` — the tools executed across the crash and the resume, in order, are exactly **get_order → search_policy → calculate_refund → issue_refund** (four executions, none repeated), final status **REFUND with INR 128.25**.

### ReAct vs plan-and-execute (task 9, 122 words)

> ReAct spends one model call per decision: measured on our runs, S1 took 5 calls (get_order, search_policy, calculate_refund, issue_refund, final answer), the cancelled-order case S5 took 3 and the unknown-order case S6 took 2, at a few hundred to a few thousand estimated tokens each. A plan-and-execute design would ask the model for the whole step list once and replan only on error: the happy path needs about 2 calls instead of 5, but an unexpected observation such as NOT_FOUND or a cancelled order invalidates the remaining planned steps and forces a replanning round trip anyway, so the saving shrinks exactly where it matters. Because each tool's arguments here depend on the previous observation, ReAct reacts to reality at every hop with no wasted plans. I would keep ReAct for this refund workflow: the sequences are short and strictly ordered, its extra calls are bounded by the max-iteration, token and time stop-safely limits, and a one-shot plan cannot anticipate which branch the order data will justify.

## Limitations and Next Steps

- **The retention list is illustrative, not an evaluation**: the Premium flag comes from the whole-window RFM that includes the September window defining the lapse label, so the overlap between the list and the lapse label is post-hoc (the model's own features remain leakage-free).
- **The lapse label window is a single month** on a 6-month synthetic history; a production model would need rolling re-labelling, drift monitoring and a real holdout forward in time.
- **Imputation is deliberately simple**: category-median delivery times and price-formula amounts are documented rules, but rare multi-modal patterns (weather, electronics OTP holds) are invisible to them; cancelled orders keep no delivery time by design.
- **TF-IDF retrieval is lexical**: paraphrases with no shared words fail; the zero-overlap experiment shows answers breaking across chunk boundaries. Next: embeddings with a small overlap sweep, and answer-bearing chunk regeneration.
- **`mock_llm.py` is a keyword engine**, not a language model: the triage accuracy ceiling and the agent's tool discipline are properties of the mock. The guardrails (validation, retries, budgets, fallbacks) are the transferable part; swapping in a hosted model means replacing one function call, with keys kept in a `.env` that `.gitignore` already excludes.
- **The web app is a read-only console over the pipeline outputs** (plus live policy/agent runs written to `live_*` files so the graded artifacts stay pristine). Next: authentication and role gating (security-team views), write-back actions (approve a human-review ticket), and CI that runs `a_validate` on every push.
