# backend/analytics/cluster_candidates.py
import os, pymongo
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from hdbscan import HDBSCAN
from dotenv import load_dotenv

def run():
    load_dotenv()
    client = pymongo.MongoClient(os.getenv("MONGO_URI"))
    db = client[os.getenv("MONGO_DB","skilllens")]
    candidates = db["candidates"]

    # 1. Load embeddings
    docs = list(candidates.find({
        "embedding": {"$exists": True, "$ne": []}
    }, {"_id": 1, "embedding": 1}))

    if not docs:
        print("⚠️ No embeddings found in candidates")
        return {"status": "no embeddings found"}

    ids = [d["_id"] for d in docs]
    X = np.array([np.array(d["embedding"], dtype=float) for d in docs])

    # 2. Normalize and cluster
    X = StandardScaler().fit_transform(X)
    clusterer = HDBSCAN(min_cluster_size=5)   # min_cluster_size can be tuned
    labels = clusterer.fit_predict(X)

    # 3. Update candidates with cluster label
    for cand_id, label in zip(ids, labels):
        label_value = int(label) if label != -1 else None
        candidates.update_one({"_id": cand_id}, {"$set": {"cluster": label_value}})

    # 4. Compute summary and save to analytics
    summary = pd.Series(labels).value_counts().to_dict()
    cluster_list = [{"cluster": int(k), "count": int(v)} for k, v in summary.items()]

    db["analytics"].update_one(
        {"name": "clusters"},
        {"$set": {"clusters": cluster_list}},
        upsert=True
    )

    print("✅ Clustering done. Candidates updated with 'cluster', summary saved to analytics.")
    return {"status": "clusters recomputed", "clusters": cluster_list}

if __name__ == "__main__":
    run()
