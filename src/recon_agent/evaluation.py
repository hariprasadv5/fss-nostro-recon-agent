"""Offline evaluation against the injected ground-truth labels (model risk / acceptance testing)."""
from __future__ import annotations

import pandas as pd


def evaluate(inv: pd.DataFrame, truth_file, out_dir) -> dict:
    truth = pd.read_csv(truth_file)
    df = truth.merge(inv[["break_id", "category", "confidence"]], left_on="item_id", right_on="break_id", how="left")
    df["predicted"] = df["category"].fillna("NOT_FOUND")
    df["correct"] = df["predicted"] == df["expected_category"]
    df[["item_id", "account_id", "expected_category", "predicted", "confidence", "correct"]].to_csv(
        out_dir / "evaluation_detail.csv", index=False)

    per_cat = {}
    for cat in sorted(set(df["expected_category"]) | set(inv["category"])):
        tp = int(((df["expected_category"] == cat) & (df["predicted"] == cat)).sum())
        fn = int(((df["expected_category"] == cat) & (df["predicted"] != cat)).sum())
        fp = int((inv["category"] == cat).sum()) - tp
        per_cat[cat] = dict(precision=round(tp / (tp + fp), 3) if tp + fp else None,
                            recall=round(tp / (tp + fn), 3) if tp + fn else None, support=tp + fn)
    sus = df[df["expected_category"] == "SUSPICIOUS"]
    return dict(labelled_breaks=len(df), accuracy=round(df["correct"].mean(), 4),
                coverage=round((df["predicted"] != "NOT_FOUND").mean(), 4),
                suspicious_escalation_rate=round((sus["predicted"] == "SUSPICIOUS").mean(), 4) if len(sus) else None,
                unlabelled_breaks=int((~inv["break_id"].isin(truth["item_id"])).sum()),
                per_category=per_cat)
