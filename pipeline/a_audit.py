"""Part A, task 2 — audit the raw exports before any cleaning.

Run:  python -m pipeline.a_audit
Loads the three raw tables with pandas, reports shape / dtypes / missing values for every
column, and records the specific audit figures the brief asks for in outputs/metrics.json.
"""

from __future__ import annotations

import json

import pandas as pd

from pipeline.paths import RAW, save_metrics


def audit_frame(df: pd.DataFrame, name: str, missing_series: pd.Series) -> dict:
    """Shape + dtype + missing-count report for one raw table."""
    columns = [
        {
            "column": col,
            "dtype": str(df[col].dtype),
            "missing": int(missing_series[col]),
            "missing_pct": round(100 * missing_series[col] / len(df), 2),
        }
        for col in df.columns
    ]
    return {"table": name, "rows": int(len(df)), "columns": int(df.shape[1]), "column_missing": columns}


def main() -> None:
    # Default read: empty fields become NaN so isna() counts blanks directly.
    customers = pd.read_csv(RAW / "customers.csv")
    orders = pd.read_csv(RAW / "orders.csv")
    # dtypes report for orders is read from a plain parse; the exact audit figures below use a
    # raw string read so "N/A"/"error"/"" are inspected exactly as they appear in the file.
    orders_text = pd.read_csv(RAW / "orders.csv", dtype=str, keep_default_na=False)

    # ---- audit figures on the raw orders table -------------------------------
    amount_num = pd.to_numeric(orders_text["order_amount"], errors="coerce")
    delivery_num = pd.to_numeric(orders_text["delivery_minutes"], errors="coerce")
    figures = {
        "raw_order_rows": int(len(orders_text)),
        "exact_duplicate_rows": int(orders_text.duplicated().sum()),
        "pending_rows": int((orders_text["status"] == "pending").sum()),
        "distinct_order_ids": int(orders_text["order_id"].nunique()),
        "non_numeric_amounts": int(amount_num.isna().sum()),
        "negative_delivery_minutes": int((delivery_num < 0).sum()),
        "blank_delivery_minutes": int((orders_text["delivery_minutes"].str.strip() == "").sum()),
        # ---- customers ----
        "blank_ages": int(customers["age"].isna().sum()),
        "ages_outside_10_100": int(((customers["age"] < 10) | (customers["age"] > 100)).sum()),
        "raw_city_spellings": int(customers["city"].nunique()),
        "raw_gender_spellings": int(customers["gender"].dropna().nunique()),
        "blank_genders": int(customers["gender"].isna().sum()),
    }

    products = pd.read_csv(RAW / "products.csv")
    tables = [
        audit_frame(customers, "customers", customers.isna().sum()),
        audit_frame(products, "products", products.isna().sum()),
        audit_frame(orders, "orders", orders.isna().sum()),
    ]

    save_metrics("audit", {"figures": figures, "tables": tables})
    print(json.dumps(figures, indent=2))


if __name__ == "__main__":
    main()
