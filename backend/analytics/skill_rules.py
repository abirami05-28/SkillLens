# backend/analytics/skill_rules.py
import os, pymongo
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
from dotenv import load_dotenv
from datetime import datetime

def run():
    load_dotenv()
    client = pymongo.MongoClient(os.getenv("MONGO_URI"))
    db = client[os.getenv("MONGO_DB", "skilllens")]

    candidates = db["candidates"]
    analytics = db["analytics"]

    # Load candidate skills
    docs = list(candidates.find({}, {"skills": 1}))
    skill_lists = [d.get("skills", []) for d in docs if d.get("skills")]

    if not skill_lists:
        print("⚠️ No skills found in candidates")
        return {"status": "no data"}

    # Convert to transaction DataFrame
    all_skills = sorted(set(s for sl in skill_lists for s in sl))
    df = pd.DataFrame([{s: (s in skills) for s in all_skills} for skills in skill_lists])

    # Run Apriori
    frequent = apriori(df, min_support=0.05, use_colnames=True)
    rules = association_rules(frequent, metric="lift", min_threshold=1.0)

    # Convert to serializable format
    rules_out = []
    for _, row in rules.iterrows():
        rules_out.append({
            "antecedents": list(row["antecedents"]),
            "consequents": list(row["consequents"]),
            "support": row["support"],
            "confidence": row["confidence"],
            "lift": row["lift"]
        })

    analytics.update_one(
        {"name": "skill_rules"},
        {"$set": {"rules": rules_out, "updated_at": datetime.utcnow()}},
        upsert=True
    )

    print(f"✅ Stored {len(rules_out)} skill rules")
    return {"status": "skills recomputed", "count": len(rules_out)}

if __name__ == "__main__":
    run()
