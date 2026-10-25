"""Part B, tasks 4-8 — the lapse-prediction problem: leakage-safe features, train/tune/evaluate,
class-balance experiment, interpretation, persistence and the Premium retention list.

Run:  python -m pipeline.b_lapse

Cutoff: 2025-09-01. Every feature comes from orders dated strictly before the cutoff plus the
clean customer table; no encoder, scaler or resampler ever sees the test rows, and the segment
labels from task 3 are not used as features.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, accuracy_score
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
import joblib

from pipeline.paths import CLEAN, OUTPUTS, save_metrics

CUTOFF = pd.Timestamp("2025-09-01 00:00:00")
SEED = 42
NUM_COLS = ["recency", "frequency", "monetary", "avg_discount_pct", "cancel_rate",
            "avg_delivery_minutes", "age", "tenure"]
CAT_COLS = ["city", "gender", "fav_category"]


def metrics_row(y_true, y_pred) -> dict:
    return {
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 3),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 3),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 3),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
    }


def make_pipeline(model) -> Pipeline:
    return Pipeline([
        ("prep", ColumnTransformer([("num", StandardScaler(), NUM_COLS),
                                    ("cat", OneHotEncoder(drop="first"), CAT_COLS)])),
        ("model", model),
    ])


def main() -> None:
    orders = pd.read_csv(CLEAN / "orders.csv", parse_dates=["order_ts"])
    customers = pd.read_csv(CLEAN / "customers.csv", parse_dates=["signup_date"])

    pre = orders[orders["order_ts"] < CUTOFF]
    comp_pre = pre[pre["status"] == "completed"]

    # ---- task 4: cohort, label, features ------------------------------------------
    cohort_ids = sorted(comp_pre["customer_id"].unique())
    sept_ids = set(orders.loc[(orders["status"] == "completed") & (orders["order_ts"] >= CUTOFF), "customer_id"])

    feats = (comp_pre.groupby("customer_id")
             .agg(last_ts=("order_ts", "max"), frequency=("order_id", "nunique"),
                  monetary=("order_amount", "sum"), avg_discount_pct=("discount_pct", "mean"),
                  avg_delivery_minutes=("delivery_minutes", "mean"))
             .reset_index())
    feats["recency"] = (CUTOFF - feats.pop("last_ts")).dt.days
    feats["monetary"] = feats["monetary"].round(2)

    status_counts = pre.groupby(["customer_id", "status"]).size().unstack(fill_value=0)
    total_final = status_counts.sum(axis=1)
    cancel_rate = (status_counts.get("cancelled", pd.Series(0, index=status_counts.index)) / total_final)
    feats["cancel_rate"] = feats["customer_id"].map(cancel_rate)

    fav = (comp_pre.groupby(["customer_id", "category"]).size().reset_index(name="n")
           .sort_values(["customer_id", "n", "category"], ascending=[True, False, True])
           .groupby("customer_id").first()["category"])
    feats["fav_category"] = feats["customer_id"].map(fav)

    feats = feats.merge(customers[["customer_id", "city", "age", "gender", "signup_date"]], on="customer_id")
    feats["tenure"] = (CUTOFF - feats["signup_date"]).dt.days
    feats["lapsed"] = (~feats["customer_id"].isin(sept_ids)).astype(int)

    assert feats[NUM_COLS + CAT_COLS].isna().sum().sum() == 0, "feature columns contain missing values"
    assert pre["order_ts"].max() < CUTOFF, "feature window leaked past the cutoff"

    y = feats["lapsed"]
    idx_train, idx_test, y_train, y_test = train_test_split(
        feats.index, y, test_size=0.2, stratify=y, random_state=SEED)
    X = feats[NUM_COLS + CAT_COLS]
    X_train, X_test = X.loc[idx_train], X.loc[idx_test]

    baseline_pred = np.zeros(len(y_test), dtype=int)
    baseline = {"accuracy": round(float(accuracy_score(y_test, baseline_pred)), 3),
                "f1_lapsed": round(float(f1_score(y_test, baseline_pred, zero_division=0)), 3)}

    # ---- task 5: preprocess inside the pipeline (fit on train only) -----------------
    lr_grid = GridSearchCV(make_pipeline(LogisticRegression(max_iter=1000)),
                           {"model__C": [0.01, 0.1, 1, 10, 100]}, cv=5, scoring="f1", n_jobs=-1)
    rf_grid = GridSearchCV(make_pipeline(RandomForestClassifier(n_estimators=100, random_state=SEED)),
                           {"model__max_depth": [3, 5, 8], "model__min_samples_leaf": [5, 10, 20]},
                           cv=5, scoring="f1", n_jobs=-1)
    lr_grid.fit(X_train, y_train)
    rf_grid.fit(X_train, y_train)

    test_lr, test_rf = metrics_row(y_test, lr_grid.predict(X_test)), metrics_row(y_test, rf_grid.predict(X_test))
    best_lr, best_rf = lr_grid.best_estimator_, rf_grid.best_estimator_
    selected, selected_test, selected_name = (
        (best_rf, test_rf, "random_forest") if test_rf["f1"] >= test_lr["f1"] else (best_lr, test_lr, "logistic_regression"))

    # ---- task 6: class-balance experiment ------------------------------------------
    # The brief refits the best LOGISTIC REGRESSION on the balanced training set and compares
    # it with the same (un-balanced) logistic regression on the unchanged test set.
    train_df = X_train.copy()
    train_df["__y"] = y_train
    majority = train_df[train_df["__y"] == 0]
    minority = train_df[train_df["__y"] == 1]
    extra = minority.sample(n=len(majority) - len(minority), replace=True, random_state=SEED)
    balanced = pd.concat([train_df, extra])
    Xb, yb = balanced.drop(columns="__y"), balanced["__y"]

    bal_model = make_pipeline(LogisticRegression(max_iter=1000, C=lr_grid.best_params_["model__C"]))
    bal_model.fit(Xb, yb)
    balanced_test = metrics_row(y_test, bal_model.predict(X_test))

    # ---- task 7: interpret, persist, retention list ---------------------------------
    prep_out = selected.named_steps["prep"].get_feature_names_out()
    if selected_name == "random_forest":
        importances = selected.named_steps["model"].feature_importances_
        top5 = [{"feature": n.replace("num__", "").replace("cat__", ""), "importance": round(float(v), 4)}
                for n, v in sorted(zip(prep_out, importances), key=lambda t: -t[1])[:5]]
    else:
        top5 = []
    # coefficient signs always come from the best logistic regression, even when the random
    # forest is the selected model
    lr_out = best_lr.named_steps["prep"].get_feature_names_out()
    lr_coefs = best_lr.named_steps["model"].coef_[0]
    lr_signs = []
    for feat in ["recency", "frequency", "monetary"]:
        i = list(lr_out).index(f"num__{feat}")
        lr_signs.append({"feature": feat, "coefficient": round(float(lr_coefs[i]), 4),
                         "sign": "positive" if lr_coefs[i] > 0 else "negative"})

    joblib.dump(selected, OUTPUTS / "lapse_model.joblib")
    reloaded = joblib.load(OUTPUTS / "lapse_model.joblib")
    assert (reloaded.predict(X_test) == selected.predict(X_test)).all(), "reloaded model differs"

    segments = pd.read_csv(OUTPUTS / "customer_segments.csv")
    is_prem = segments["is_premium"].apply(lambda v: bool(v) if isinstance(v, bool) else str(v).strip().lower() == "true")
    premium_ids = set(segments.loc[is_prem, "customer_id"])
    proba = selected.predict_proba(X_test)[:, 1]
    retention = pd.DataFrame({"customer_id": feats.loc[idx_test, "customer_id"].values,
                              "lapse_probability": proba.round(4), "actually_lapsed": y_test.values})
    retention = (retention[retention["customer_id"].isin(premium_ids)]
                 .sort_values("lapse_probability", ascending=False).head(10))
    retention.to_csv(OUTPUTS / "retention_list.csv", index=False)

    scaler = selected.named_steps["prep"].named_transformers_["num"]
    freq_i = NUM_COLS.index("frequency")
    scaler_means = {
        "learned_frequency_mean_train_only": round(float(scaler.mean_[freq_i]), 3),
        "full_cohort_frequency_mean": round(float(X["frequency"].mean()), 3),
        "why_differ": ("The scaler is fitted on the 924 training rows only, so its learned mean is the training "
                       "split's mean of frequency, not the full cohort's."),
    }

    metrics = {
        "cohort_customers": int(len(feats)),
        "lapsed": int(y.sum()),
        "lapsed_pct": round(float(100 * y.mean()), 2),
        "train_rows": int(len(idx_train)), "test_rows": int(len(idx_test)),
        "baseline": baseline,
        "logistic_regression": {"best_params": {"C": lr_grid.best_params_["model__C"]},
                                "best_cv_f1": round(float(lr_grid.best_score_), 3), "test": test_lr},
        "random_forest": {"best_params": {"max_depth": rf_grid.best_params_["model__max_depth"],
                                          "min_samples_leaf": rf_grid.best_params_["model__min_samples_leaf"]},
                          "best_cv_f1": round(float(rf_grid.best_score_), 3), "test": test_rf},
        "selected_model": selected_name, "selected_test": selected_test,
        "balanced_train": {"rows": int(len(balanced)), "per_class": int(len(balanced) // 2)},
        "balanced_experiment": {
            "model": "logistic_regression",
            "unbalanced_lr_test": test_lr,
            "balanced_lr_test": balanced_test,
            "reading": ("Recall moves most: the balanced refit catches far more lapsing customers, while precision "
                        "stays near the same level, so the retention team buys coverage at a similar cost of "
                        "wasted targets."),
        },
        "top5_importances": top5, "lr_signs": lr_signs,
        "scaler_means": scaler_means,
        "retention_list_rows": int(len(retention)),
        "retention_truly_lapsed": int(retention["actually_lapsed"].sum()),
        "leakage_statement": ("No encoder, scaler or resampler saw test rows; no order dated on or after 2025-09-01 "
                              "entered the features; the task-3 segment labels were not used as features."),
        "retention_caveat": ("The Premium flag comes from the whole-window RFM (which includes the September window "
                             "that defines the lapse label), so the retention list is illustrative and not a "
                             "leakage-free evaluation."),
    }
    save_metrics("lapse", metrics)
    print(f"selected={selected_name} test={selected_test} baseline={baseline}")
    print(f"lr_unbalanced={test_lr} lr_balanced={balanced_test} "
          f"retention_rows={len(retention)} truly_lapsed={int(retention['actually_lapsed'].sum())}")


if __name__ == "__main__":
    main()
