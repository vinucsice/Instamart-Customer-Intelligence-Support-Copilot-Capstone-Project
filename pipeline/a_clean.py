"""Part A, tasks 3-4 — clean customers and orders with documented, ordered rules,
then store the clean tables as CSV files and in the SQLite database.

Run:  python -m pipeline.a_clean

Cleaning rules (each rule's change count is recorded in outputs/metrics.json):
  customers: strip+title city; map gender spellings to male/female/unknown; ages outside
             10-100 become missing then are filled with the median age of the customer's
             city (groupby + transform); signup_date parsed as a datetime.
  orders:    parse order_ts; drop exact duplicate rows; for each order_id keep only the
             record with the latest order_ts; order_amount to numeric with unparseable
             entries refilled as round(price*qty*(1-discount/100), 2); negative
             delivery_minutes to missing; completed orders get missing delivery_minutes
             filled with the median of the product category among completed orders;
             cancelled orders keep a missing delivery time (never delivered).
"""

from __future__ import annotations

import sqlite3

import pandas as pd

from pipeline.paths import CLEAN, DB_PATH, RAW, save_metrics


def main() -> None:
    customers_rules: list[dict] = []
    orders_rules: list[dict] = []

    # ------------------------------------------------------------------ customers
    cust = pd.read_csv(RAW / "customers.csv")

    raw_city = cust["city"].fillna("")
    cust["city"] = raw_city.str.strip().str.title()
    customers_rules.append({"step": 1, "rule": "City standardised: strip spaces + title case -> exactly 6 cities",
                            "changed": int((raw_city != cust["city"]).sum())})

    raw_gender = cust["gender"].fillna("")
    gender_map = {"male": "male", "m": "male", "female": "female", "f": "female"}
    cust["gender"] = raw_gender.str.strip().str.lower().map(gender_map).fillna("unknown")
    customers_rules.append({"step": 2, "rule": "Gender mapped to male/female/unknown (blank -> unknown)",
                            "changed": int((raw_gender.str.strip().str.lower() != cust["gender"]).sum())})

    out_of_range = ((cust["age"] < 10) | (cust["age"] > 100)).sum()
    cust.loc[(cust["age"] < 10) | (cust["age"] > 100), "age"] = pd.NA
    missing_before = int(cust["age"].isna().sum())
    cust["age"] = cust.groupby("city")["age"].transform(lambda s: s.fillna(s.median()))
    customers_rules.append({"step": 3, "rule": "Ages outside 10-100 set to missing, then filled with the median age of the customer's city (groupby + transform)",
                            "changed": int(missing_before), "of_which_out_of_range": int(out_of_range)})

    cust["signup_date"] = pd.to_datetime(cust["signup_date"])
    customers_rules.append({"step": 4, "rule": "signup_date converted to a datetime", "changed": int(len(cust))})

    # ------------------------------------------------------------------ orders
    orders = pd.read_csv(RAW / "orders.csv", dtype=str, keep_default_na=False)
    n_raw = len(orders)

    orders["order_ts"] = pd.to_datetime(orders["order_ts"], format="%Y-%m-%d %H:%M:%S")
    orders_rules.append({"step": 1, "rule": "order_ts converted to a datetime", "changed": int(n_raw)})

    before = len(orders)
    orders = orders.drop_duplicates().copy()
    orders_rules.append({"step": 2, "rule": "Exact duplicate rows removed", "changed": int(before - len(orders))})

    before = len(orders)
    orders = orders.sort_values("order_ts", kind="mergesort").drop_duplicates("order_id", keep="last").copy()
    orders_rules.append({"step": 3, "rule": "Kept only the record with the latest order_ts per order_id (drops the earlier 'pending' records)",
                         "changed": int(before - len(orders))})

    products = pd.read_csv(RAW / "products.csv")
    price = products.set_index("product_id")["price_inr"]
    category = products.set_index("product_id")["category"]
    orders["category"] = orders["product_id"].map(category)
    orders["quantity"] = orders["quantity"].astype(int)
    orders["discount_pct"] = orders["discount_pct"].astype(int)
    orders["price_inr"] = orders["product_id"].map(price)

    amount = pd.to_numeric(orders["order_amount"], errors="coerce")
    unparseable = int(amount.isna().sum())
    refill = (orders["price_inr"] * orders["quantity"] * (1 - orders["discount_pct"] / 100)).round(2)
    orders["order_amount"] = amount.fillna(refill).round(2)
    orders_rules.append({"step": 4, "rule": "order_amount to numeric; unparseable entries refilled as round(price*qty*(1-discount/100), 2)",
                         "changed": unparseable})

    delivery = pd.to_numeric(orders["delivery_minutes"], errors="coerce")
    negatives = int((delivery < 0).sum())
    delivery[delivery < 0] = pd.NA
    orders["delivery_minutes"] = delivery
    orders_rules.append({"step": 5, "rule": "Negative delivery_minutes set to missing", "changed": negatives})

    completed = orders["status"] == "completed"
    median_by_cat = orders.loc[completed].groupby("category")["delivery_minutes"].median()
    fill_mask = completed & orders["delivery_minutes"].isna()
    orders.loc[fill_mask, "delivery_minutes"] = orders.loc[fill_mask, "category"].map(median_by_cat)
    orders_rules.append({"step": 6, "rule": "Completed orders: missing delivery_minutes filled with the category median among completed orders",
                         "changed": int(fill_mask.sum())})
    cancelled_missing = int((orders["status"] == "cancelled").sum())
    orders_rules.append({"step": 7, "rule": "Cancelled orders: delivery_minutes left missing (never delivered, imputing would invent data)",
                         "changed": cancelled_missing})

    orders = orders[["order_id", "customer_id", "product_id", "quantity", "order_ts", "status",
                     "discount_pct", "order_amount", "delivery_minutes", "category"]].sort_values("order_id")

    # ------------------------------------------------------------------ store
    cust_out = cust.copy()
    cust_out["signup_date"] = cust_out["signup_date"].dt.strftime("%Y-%m-%d")
    orders_out = orders.copy()
    orders_out["order_ts"] = orders_out["order_ts"].dt.strftime("%Y-%m-%d %H:%M:%S")

    cust_out.to_csv(CLEAN / "customers.csv", index=False)
    products.to_csv(CLEAN / "products.csv", index=False)
    orders_out.to_csv(CLEAN / "orders.csv", index=False)

    conn = sqlite3.connect(DB_PATH)
    try:
        cust_out.to_sql("customers", conn, if_exists="replace", index=False)
        products.to_sql("products", conn, if_exists="replace", index=False)
        orders_out.to_sql("orders", conn, if_exists="replace", index=False)
        conn.commit()
    finally:
        conn.close()

    status_counts = orders["status"].value_counts().to_dict()
    after = {
        "order_rows": int(len(orders)),
        "completed": int(status_counts.get("completed", 0)),
        "cancelled": int(status_counts.get("cancelled", 0)),
        "pending": int(status_counts.get("pending", 0)),
        "missing_order_amount": int(orders["order_amount"].isna().sum()),
        "missing_delivery_completed": int(orders.loc[completed, "delivery_minutes"].isna().sum()),
        "missing_delivery_cancelled": int(orders.loc[~completed, "delivery_minutes"].isna().sum()),
        "completed_amount_sum": round(float(orders.loc[completed, "order_amount"].sum()), 2),
    }
    summary = {
        "customers_rules": customers_rules,
        "orders_rules": orders_rules,
        "city_counts": cust["city"].value_counts().to_dict(),
        "gender_counts": cust["gender"].value_counts().to_dict(),
        "age_min": float(cust["age"].min()),
        "age_max": float(cust["age"].max()),
        "missing_ages": int(cust["age"].isna().sum()),
        "after": after,
    }
    save_metrics("cleaning", summary)
    print(summary["after"])


if __name__ == "__main__":
    main()
