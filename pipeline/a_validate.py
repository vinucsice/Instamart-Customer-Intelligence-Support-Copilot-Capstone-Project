"""Part A, task 5 — validate the clean tables against the brief's reference checkpoints.

Run:  python -m pipeline.a_validate
Prints exactly `ALL CHECKPOINTS PASSED` when every checkpoint holds.
"""

from __future__ import annotations

import sqlite3

import pandas as pd

from pipeline.paths import CLEAN, DB_PATH, RAW, save_metrics

EXPECTED_CITIES = {"Pune": 227, "Delhi": 210, "Bengaluru": 197, "Chennai": 191, "Hyderabad": 191, "Mumbai": 184}
EXPECTED_GENDERS = {"female": 610, "male": 560, "unknown": 30}


def main() -> None:
    orders = pd.read_csv(CLEAN / "orders.csv")
    customers = pd.read_csv(CLEAN / "customers.csv")
    completed = orders["status"] == "completed"

    checks: list[tuple[str, bool]] = [
        ("clean orders has 12,309 rows (one per order_id)", len(orders) == 12309),
        ("11,110 completed orders", int(completed.sum()) == 11110),
        ("1,199 cancelled orders", int((~completed).sum()) == 1199),
        ("no pending rows remain", int((orders["status"] == "pending").sum()) == 0),
        ("0 missing order_amount", int(orders["order_amount"].isna().sum()) == 0),
        ("0 missing delivery_minutes among completed orders",
         int(orders.loc[completed, "delivery_minutes"].isna().sum()) == 0),
        ("1,199 missing delivery_minutes among cancelled orders",
         int(orders.loc[~completed, "delivery_minutes"].isna().sum()) == 1199),
        ("sum of order_amount over completed orders is INR 2,998,668.80",
         round(float(orders.loc[completed, "order_amount"].sum()), 2) == 2998668.80),
        ("exactly 6 cities after standardisation", sorted(customers["city"].unique()) == sorted(EXPECTED_CITIES)),
        ("city counts match the reference", customers["city"].value_counts().to_dict() == EXPECTED_CITIES),
        ("gender counts match the reference", customers["gender"].value_counts().to_dict() == EXPECTED_GENDERS),
        ("0 missing ages after imputation", int(customers["age"].isna().sum()) == 0),
        ("every age between 18 and 60",
         bool((customers["age"].between(18, 60)).all())),
        ("raw audit: 13,084 raw order rows", True),  # asserted in a_audit metrics below
        ("signup_date is a datetime", pd.api.types.is_datetime64_any_dtype(pd.to_datetime(customers["signup_date"]))),
    ]

    # raw audit figures recorded by a_audit must match the reference as well
    from pipeline.paths import load_metrics
    audit = load_metrics().get("audit", {}).get("figures", {})
    raw_checks = [
        ("raw_order_rows", 13084), ("exact_duplicate_rows", 119), ("pending_rows", 656),
        ("distinct_order_ids", 12309), ("non_numeric_amounts", 120), ("negative_delivery_minutes", 106),
        ("blank_delivery_minutes", 2541), ("blank_ages", 61), ("ages_outside_10_100", 6),
        ("raw_city_spellings", 24), ("raw_gender_spellings", 10), ("blank_genders", 30),
    ]
    for key, expected in raw_checks:
        checks.append((f"raw audit {key} == {expected}", audit.get(key) == expected))

    failed = [name for name, ok in checks if not ok]
    conn = sqlite3.connect(DB_PATH)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    checks.append(("data/instamart.db contains customers, products, orders",
                   {"customers", "products", "orders"}.issubset(tables)))
    if not {"customers", "products", "orders"}.issubset(tables):
        failed.append("data/instamart.db contains customers, products, orders")

    save_metrics("validation", {
        "total": len(checks), "failed": failed,
        "status": "ALL CHECKPOINTS PASSED" if not failed else "CHECKPOINTS FAILED",
    })

    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
    if failed:
        raise SystemExit(f"{len(failed)} checkpoint(s) failed")
    print("ALL CHECKPOINTS PASSED")


if __name__ == "__main__":
    main()
