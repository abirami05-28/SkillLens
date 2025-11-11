# backend/analytics/fairness_eval.py
import os, pymongo, pandas as pd, math
from aif360.datasets import StandardDataset
from aif360.metrics import ClassificationMetric
from dotenv import load_dotenv
from datetime import datetime

def safe_float(x):
    """Convert NaN/inf to None so JSON and Mongo can handle it."""
    try:
        if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
            return None
        return float(x)
    except Exception:
        return None

def run():
    load_dotenv()
    client = pymongo.MongoClient(os.getenv("MONGO_URI"))
    db = client[os.getenv("MONGO_DB", "skilllens")]
    c = db["candidates"]

    # Fetch candidates
    docs = list(c.find({}, {"gender": 1, "age": 1, "model_score": 1}))
    if not docs:
        print("⚠️ No candidates found in DB")
        return {"status": "no candidates found"}

    df = pd.DataFrame(docs)
    df["label"] = df["model_score"].apply(lambda x: 1 if (pd.notnull(x) and x >= 0.5) else 0)

    results_all = {}
    if df["label"].sum() == 0:
        print("⚠️ No positive labels found for fairness metrics.")
        return {"status": "no valid labels"}

    # ---------- Gender ----------
    if "gender" in df.columns:
        dataset = StandardDataset(
            df[["label", "gender"]],
            label_name="label",
            favorable_classes=[1],
            protected_attribute_names=["gender"],
            privileged_classes=[["Male"]],
        )
        metric = ClassificationMetric(
            dataset, dataset,
            unprivileged_groups=[{"gender": "Female"}],
            privileged_groups=[{"gender": "Male"}]
        )
        gender_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "statistical_parity": safe_float(metric.statistical_parity_difference()),
            "disparate_impact": safe_float(metric.disparate_impact()),
            "equal_opportunity_diff": safe_float(metric.equal_opportunity_difference()),
            "average_odds_diff": safe_float(metric.average_odds_difference())
        }
        db["bias_metrics"].update_one(
            {"attribute": "gender"},
            {"$set": gender_results},
            upsert=True
        )
        results_all["gender"] = gender_results
        print("✅ Fairness evaluation saved for gender")

    # ---------- Age ----------
    if "age" in df.columns:
        df["age_group"] = df["age"].apply(lambda x: "30_plus" if x and x >= 30 else "under_30")
        dataset = StandardDataset(
            df[["label", "age_group"]],
            label_name="label",
            favorable_classes=[1],
            protected_attribute_names=["age_group"],
            privileged_classes=[["30_plus"]],
        )
        metric = ClassificationMetric(
            dataset, dataset,
            unprivileged_groups=[{"age_group": "under_30"}],
            privileged_groups=[{"age_group": "30_plus"}]
        )
        age_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "statistical_parity": safe_float(metric.statistical_parity_difference()),
            "disparate_impact": safe_float(metric.disparate_impact()),
            "equal_opportunity_diff": safe_float(metric.equal_opportunity_difference()),
            "average_odds_diff": safe_float(metric.average_odds_difference())
        }
        db["bias_metrics"].update_one(
            {"attribute": "age"},
            {"$set": age_results},
            upsert=True
        )
        results_all["age"] = age_results
        print("✅ Fairness evaluation saved for age")

    return {"status": "fairness recomputed", "results": results_all}

if __name__ == "__main__":
    run()
