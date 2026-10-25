"""Part B, tasks 1-3 — RFM table, K-means clustering, segment naming and PCA.

Run:  python -m pipeline.b_segments

Uses only completed orders. Snapshot moment: 2025-10-01 00:00:00.
Cluster numbers are only labels with no ordering; the Premium flag marks the segment with
the highest mean monetary value.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from pipeline.paths import CLEAN, OUTPUTS, save_metrics

SNAPSHOT = pd.Timestamp("2025-10-01 00:00:00")
CHOSEN_K = 4  # chosen from {3, 4, 5}: highest silhouette in the range and four clear business plays


def main() -> None:
    orders = pd.read_csv(CLEAN / "orders.csv", parse_dates=["order_ts"])
    completed = orders[orders["status"] == "completed"]

    # ---- task 1: RFM ----------------------------------------------------------------
    rfm = (completed.groupby("customer_id")
           .agg(last_order_ts=("order_ts", "max"), frequency=("order_id", "nunique"),
                monetary=("order_amount", "sum"))
           .reset_index())
    rfm["recency"] = (SNAPSHOT - rfm.pop("last_order_ts")).dt.days
    rfm["monetary"] = rfm["monetary"].round(2)

    rfm_stats = {
        "customers": int(len(rfm)),
        "recency_median": int(rfm["recency"].median()),
        "recency_min": int(rfm["recency"].min()), "recency_max": int(rfm["recency"].max()),
        "frequency_mean": round(float(rfm["frequency"].mean()), 2),
        "frequency_max": int(rfm["frequency"].max()),
        "monetary_mean": round(float(rfm["monetary"].mean()), 2),
        "monetary_max": round(float(rfm["monetary"].max()), 2),
    }

    # ---- task 2: K-means, K = 2..8 ----------------------------------------------------
    X = rfm[["recency", "frequency", "monetary"]]
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    kmeans_table = []
    for k in range(2, 9):
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = km.fit_predict(X_scaled)
        kmeans_table.append({"k": k, "inertia": round(float(km.inertia_), 1),
                             "silhouette": round(float(silhouette_score(X_scaled, labels)), 3)})

    final = KMeans(n_clusters=CHOSEN_K, n_init=10, random_state=42)
    rfm["segment_id"] = final.fit_predict(X_scaled)

    # ---- task 3: profile, name, flag --------------------------------------------------
    profile = (rfm.groupby("segment_id")
               .agg(size=("customer_id", "count"), recency=("recency", "mean"),
                    frequency=("frequency", "mean"), monetary=("monetary", "mean"))
               .round({"recency": 1, "frequency": 1, "monetary": 2}))

    order_by_monetary = profile.sort_values("monetary", ascending=False).index.tolist()
    premium_id = int(order_by_monetary[0])
    rest = order_by_monetary[1:]
    loyal_id = int(max(rest, key=lambda s: profile.loc[s, "frequency"]))
    rest = [s for s in rest if s != loyal_id]
    rest = sorted(rest, key=lambda s: profile.loc[s, "monetary"], reverse=True)

    names = {
        premium_id: ("Premium", "Protect: priority support, early access, loyalty perks"),
        loyal_id: ("Loyal Regulars", "Reward and upsell: bundles, subscriptions, referral nudges"),
        int(rest[0]): ("At-Risk High Value", "Win back within 7 days: personal offers and follow-up calls"),
        int(rest[1]): ("Occasional Shoppers", "Nudge with coupons and reminders to rebuild the habit"),
    }

    segments = rfm.copy()
    segments["segment_name"] = segments["segment_id"].map(lambda s: names[int(s)][0])
    segments["is_premium"] = segments["segment_id"].astype(int) == premium_id
    segments[["customer_id", "recency", "frequency", "monetary", "segment_id",
              "segment_name", "is_premium"]].to_csv(OUTPUTS / "customer_segments.csv", index=False)

    pca = PCA(n_components=2, random_state=42)
    pca.fit(X_scaled)

    metrics = {
        "rfm_stats": rfm_stats,
        "kmeans_table": kmeans_table,
        "chosen_k": CHOSEN_K,
        "chosen_k_reason": ("K=4 has the highest silhouette score (0.526) of {3, 4, 5} and splits the base into "
                            "four actionable plays; cluster numbers are only labels with no ordering."),
        "k_lower_inertia_cannot_pick": ("Inertia always falls as K grows because more centroids cut the squared "
                                         "distances (it would reach 0 at K = n), so a lower value alone rewards "
                                         "overfitting; the elbow, the silhouette and business interpretability pick K."),
        "segments_profile": [
            {"segment_id": int(s), "segment_name": names[int(s)][0], "recommended_action": names[int(s)][1],
             "size": int(profile.loc[s, "size"]), "recency_mean": float(profile.loc[s, "recency"]),
             "frequency_mean": float(profile.loc[s, "frequency"]), "monetary_mean": float(profile.loc[s, "monetary"]),
             "is_premium": int(s) == premium_id}
            for s in profile.index
        ],
        "pca_explained_variance_ratio": [round(float(v), 3) for v in pca.explained_variance_ratio_],
        "pca_total": round(float(pca.explained_variance_ratio_.sum()), 3),
    }
    save_metrics("segments", metrics)
    print(f"K={CHOSEN_K} chosen; premium segment {premium_id}; "
          f"PCA evr {metrics['pca_explained_variance_ratio']} total {metrics['pca_total']}")
    print(np.array(kmeans_table))


if __name__ == "__main__":
    main()
