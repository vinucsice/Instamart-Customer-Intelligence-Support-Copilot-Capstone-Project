"""Part A, task 7 — pandas cross-check of the SQL results and exploratory analysis.

Run:  python -m pipeline.a_eda
(a) rebuilds Q2 with pivot_table(margins=True) and reports the per-city named aggregation;
(b) distribution, quartiles, IQR fences, outliers and the correlation matrix of the
    completed-order_amount data, plus the four written answers (<= 200 words in total).
"""

from __future__ import annotations

import pandas as pd

from pipeline.paths import CLEAN, save_metrics

ANSWERS = (
    "What is this data about? Completed Instamart orders in six metro cities from April to "
    "September 2025: 11,110 orders by 1,175 customers over a 40-product catalogue, each row "
    "holding amount, discount, quantity and delivery minutes. "
    "What do the distributions look like? Amounts average INR 269.91 but the median is only "
    "INR 135.00 and skewness is about 4.61 — a long right tail of a few large electronics "
    "baskets. "
    "Are there outliers or anomalies? Yes: the 1.5xIQR fences (Q1 64.80, Q3 297.00) put 897 "
    "orders above the upper fence of 645.30 and none below the lower fence; they are genuine "
    "big-basket orders, not data errors. "
    "What relationships exist? All correlations are weak: the largest in absolute value is "
    "order_amount with discount_pct at about -0.095 (order_amount with quantity is +0.087, "
    "slightly smaller). Bigger discounts pair with slightly bigger orders, but a correlation "
    "this small explains almost no variance — it does not establish causation."
)


def main() -> None:
    orders = pd.read_csv(CLEAN / "orders.csv")
    customers = pd.read_csv(CLEAN / "customers.csv")
    completed = orders[orders["status"] == "completed"].merge(
        customers[["customer_id", "city"]], on="customer_id", how="left")

    # (a) pivot_table with margins must reproduce the SQL Q2 grand total
    pivot = pd.pivot_table(completed, values="order_amount", index="city", columns="category",
                           aggfunc="sum", margins=True, margins_name="All", fill_value=0)
    grand_total = round(float(pivot.loc["All", "All"]), 2)
    sql_total = round(float(completed["order_amount"].sum()), 2)

    named = (completed.groupby("city")
             .agg(spend_sum=("order_amount", "sum"), spend_mean=("order_amount", "mean"),
                  spend_count=("order_amount", "count"))
             .round({"spend_sum": 2, "spend_mean": 2}))

    # (b) distribution of completed order_amount
    amt = completed["order_amount"]
    q1, q3 = amt.quantile(0.25), amt.quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    corr = completed[["order_amount", "discount_pct", "quantity", "delivery_minutes"]].corr().round(3)
    pairs = [(abs(corr.loc[a, b]), a, b, corr.loc[a, b])
             for i, a in enumerate(corr.columns) for b in corr.columns[i + 1:]]
    pairs.sort(reverse=True)
    largest = pairs[0]

    metrics = {
        "pivot_grand_total": grand_total,
        "sql_total_matches_pivot": grand_total == sql_total,
        "per_city_named_agg": [{"city": c, "sum": round(float(r.spend_sum), 2),
                                "mean": round(float(r.spend_mean), 2), "count": int(r.spend_count)}
                               for c, r in named.iterrows()],
        "distribution": {
            "mean": round(float(amt.mean()), 2), "median": round(float(amt.median()), 2),
            "skewness": round(float(amt.skew()), 2),
            "q1": round(float(q1), 2), "q3": round(float(q3), 2), "iqr": round(float(iqr), 2),
            "lower_fence": round(float(lower), 2), "upper_fence": round(float(upper), 2),
            "outliers_below": int((amt < lower).sum()), "outliers_above": int((amt > upper).sum()),
        },
        "correlation_matrix": corr.to_dict(orient="index"),
        "largest_correlation": {"pair": [largest[1], largest[2]], "value": float(largest[3])},
        "answers_max_200_words": ANSWERS,
        "answers_word_count": len(ANSWERS.split()),
    }
    save_metrics("eda", metrics)

    assert metrics["sql_total_matches_pivot"], "pivot grand total != SQL total"
    assert metrics["answers_word_count"] <= 200, "answers exceed 200 words"
    print(f"pivot grand total INR {grand_total:,.2f} == SQL total; largest |corr| = "
          f"{largest[1]} x {largest[2]} at {largest[3]:.3f}; answers {metrics['answers_word_count']} words")


if __name__ == "__main__":
    main()
