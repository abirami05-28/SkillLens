# backend/analytics/bias_summary.py
import os, pymongo, pandas as pd, math
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
    docs = list(c.find({}, {"gender": 1, "age": 1, "model_score": 1, "cluster": 1}))
    if not docs:
        print("⚠️ No candidate documents found in DB")
        return {"status": "no candidates found"}

    df = pd.DataFrame(docs)

    # Handle missing values
    df["gender"] = df["gender"].fillna("Unknown")
    df["age_group"] = pd.cut(
        df["age"].fillna(-1),
        bins=[-1,24,34,44,200],
        labels=["<25","25-34","35-44","45+"]
    )

    # Selection rate
    df["selected"] = df["model_score"].apply(lambda x: 1 if (pd.notnull(x) and x >= 0.5) else 0)
    results_all = {}

    # --- Gender Metrics ---
    gender_selection = df.groupby("gender")["selected"].mean().to_dict()
    gender_avg_score = df.groupby("gender")["model_score"].mean().to_dict()

    db["bias_metrics"].update_one(
        {"attribute": "gender"},
        {"$set": {
            "timestamp": str(datetime.utcnow()),
            "selection_rate": gender_selection,
            "avg_score": gender_avg_score
        }},
        upsert=True
    )

    # --- Age Metrics ---
    age_selection = df.groupby("age_group")["selected"].mean().to_dict()
    age_avg_score = df.groupby("age_group")["model_score"].mean().to_dict()

    db["bias_metrics"].update_one(
        {"attribute": "age"},
        {"$set": {
            "timestamp": str(datetime.utcnow()),
            "selection_rate": age_selection,
            "avg_score": age_avg_score
        }},
        upsert=True
    )
    results_all["age"] = {"selection_rate": age_selection, "avg_score": age_avg_score}

    print("✅ Bias summary saved to bias_metrics collection (gender & age)")
    return {"status": "bias summary recomputed", "results": results_all}

if __name__ == "__main__":
    run()
