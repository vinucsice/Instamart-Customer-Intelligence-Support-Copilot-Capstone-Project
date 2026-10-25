"""Part A, task 6 — run the seven queries from sql/queries.sql against data/instamart.db
with pd.read_sql_query, assert the reference results and store them for the web UI.

Run:  python -m pipeline.a_sql
"""

from __future__ import annotations

import json
import re
import sqlite3

import pandas as pd

from pipeline.paths import DB_PATH, OUTPUTS, SQL_DIR, save_metrics

REFERENCES = {
    "q1": {"rows": 30},
    "q2": {"rows": 30, "total": 2998668.80, "max_cell": ("Bengaluru", "Electronics", 233909.45)},
    "q3": {"rows": 11},
    "q4": {"rows": 25},
    "q5": {"rows": 550, "avg": 2552.06},
    "q6": {"top_per_city": {"Bengaluru": ("C0082", 12856.20), "Chennai": ("C0930", 10151.40),
                            "Delhi": ("C0291", 13742.60), "Hyderabad": ("C0743", 12730.05),
                            "Mumbai": ("C0693", 14766.55), "Pune": ("C0426", 10377.10)},
           "rank_ne_row_number": 8},
    "q7": {"rows": 183, "last_cumulative": 2998668.80},
}


def split_queries(text: str) -> list[tuple[str, str]]:
    """Split queries.sql into (label, statement) pairs on the `-- Qn:` marker comments."""
    blocks: list[tuple[str, str]] = []
    label, buf = None, []
    for line in text.splitlines():
        m = re.match(r"^-- (Q\d+):", line)
        if m:
            if label:
                blocks.append((label, "\n".join(buf).strip().rstrip(";")))
            label, buf = m.group(1).lower(), []
        elif label is not None:
            buf.append(line)
    if label:
        blocks.append((label, "\n".join(buf).strip().rstrip(";")))
    return blocks


def main() -> None:
    queries = split_queries(SQL_DIR.joinpath("queries.sql").read_text(encoding="utf-8"))
    assert len(queries) == 7, f"expected 7 queries, found {len(queries)}"

    conn = sqlite3.connect(DB_PATH)
    failures: list[str] = []
    results: dict[str, dict] = {}
    try:
        for label, sql in queries:
            df = pd.read_sql_query(sql, conn)
            results[label] = {"sql": sql.strip(), "rows": int(len(df)),
                              "columns": list(df.columns), "data": df.to_dict(orient="records")}
            expected_rows = REFERENCES[label].get("rows")
            if expected_rows is not None and len(df) != expected_rows:
                failures.append(f"{label}: {len(df)} rows, expected {expected_rows}")

        q2 = pd.DataFrame(results["q2"]["data"])
        q2_total = round(float(q2["revenue"].sum()), 2)
        q2_top = (q2.iloc[0]["city"], q2.iloc[0]["category"], round(float(q2.iloc[0]["revenue"]), 2))
        if q2_total != REFERENCES["q2"]["total"]:
            failures.append(f"q2: total {q2_total}, expected {REFERENCES['q2']['total']}")
        if q2_top != REFERENCES["q2"]["max_cell"]:
            failures.append(f"q2: top cell {q2_top}, expected {REFERENCES['q2']['max_cell']}")

        q5 = pd.DataFrame(results["q5"]["data"])
        q5_avg = round(float(q5["avg_total_spend"].iloc[0]), 2)
        if q5_avg != REFERENCES["q5"]["avg"]:
            failures.append(f"q5: average {q5_avg}, expected {REFERENCES['q5']['avg']}")

        q6 = pd.DataFrame(results["q6"]["data"])
        q6_tops = q6[q6["rnk"] == 1].set_index("city")
        q6_top_list = [{"city": c, "customer_id": r["customer_id"], "total_spend": round(float(r["total_spend"]), 2)}
                       for c, r in q6_tops.iterrows()]
        for city, (cid, amt) in REFERENCES["q6"]["top_per_city"].items():
            row = q6_tops.loc[city]
            if row["customer_id"] != cid or round(float(row["total_spend"]), 2) != amt:
                failures.append(f"q6: top {city} = {row['customer_id']} {row['total_spend']}, expected {cid} {amt}")
        q6_rank_ne_rownum = int((q6["rnk"] != q6["row_num"]).sum())
        if q6_rank_ne_rownum != REFERENCES["q6"]["rank_ne_row_number"]:
            failures.append(f"q6: {q6_rank_ne_rownum} rows with RANK != ROW_NUMBER, expected 8")

        q7 = pd.DataFrame(results["q7"]["data"])
        q7_last = round(float(q7["cumulative_revenue"].iloc[-1]), 2)
        if q7_last != REFERENCES["q7"]["last_cumulative"]:
            failures.append(f"q7: last cumulative {q7_last}, expected {REFERENCES['q7']['last_cumulative']}")
    finally:
        conn.close()

    metrics = {
        "q1_customers": int(len(results["q1"]["data"])),
        "q2_rows": int(len(results["q2"]["data"])), "q2_total": q2_total,
        "q2_max_cell": {"city": q2_top[0], "category": q2_top[1], "revenue": q2_top[2]},
        "q3_products": int(len(results["q3"]["data"])),
        "q4_customers": int(len(results["q4"]["data"])),
        "q5_customers": int(len(results["q5"]["data"])), "q5_average": q5_avg,
        "q6_top_per_city": q6_top_list,
        "q6_rank_ne_row_number": q6_rank_ne_rownum,
        "q7_days": int(len(results["q7"]["data"])), "q7_last_cumulative": q7_last,
        "all_queries_match_references": not failures, "failures": failures,
    }
    OUTPUTS.joinpath("sql_results.json").write_text(
        json.dumps({"results": results, "metrics": metrics}, indent=2, default=str), encoding="utf-8")
    save_metrics("sql", metrics)
    if failures:
        raise SystemExit("; ".join(failures))
    print("all 7 queries match the reference results")


if __name__ == "__main__":
    main()
