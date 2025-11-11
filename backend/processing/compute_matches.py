# backend/processing/compute_matches.py
import os, sys, argparse
import pymongo
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "skilllens")

if not MONGO_URI:
    print("ERROR: MONGO_URI missing in .env")
    sys.exit(1)

client = pymongo.MongoClient(MONGO_URI)
db = client[MONGO_DB]
candidates = db["candidates"]
jobs = db["jobs"]
matches = db["matches"]

def jaccard(set1, set2):
    s1, s2 = set(set1), set(set2)
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / len(s1 | s2)

def compute_matches(top_k=5):
    all_candidates = list(candidates.find({"embedding": {"$exists": True}}))
    print(f"Loaded {len(all_candidates)} candidates")

    for job in jobs.find({"embedding": {"$exists": True}}):
        job_emb = np.array(job["embedding"]).reshape(1, -1)
        results = []

        for cand in all_candidates:
            cand_emb = np.array(cand["embedding"]).reshape(1, -1)
            cos_sim = cosine_similarity(job_emb, cand_emb)[0][0]

            jac_sim = jaccard(
                job.get("skills", []),
                cand.get("skills", [])
            )

            # get model_score if exists
            model_score = float(cand.get("model_score", 0.0))

            # combine them (you can tune weights!)
            final_score = 0.5 * cos_sim + 0.2 * jac_sim + 0.3 * model_score

            results.append({
                "candidate_id": str(cand["_id"]),
                "name": cand.get("name"),
                "cosine": float(cos_sim),
                "jaccard": float(jac_sim),
                "model_score": model_score,
                "score": float(final_score)
            })

        # keep top_k
        results = sorted(results, key=lambda x: x["score"], reverse=True)[:top_k]

        matches.update_one(
            {"job_id": job.get("job_id")},
            {"$set": {
                "job_id": job.get("job_id"),
                "job_title": job.get("title"),
                "computed_at": datetime.utcnow(),
                "matches": results
            }},
            upsert=True
        )

        print(f"Stored matches for job {job.get('job_id')} - {job.get('title')}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--top_k", type=int, default=5)
    args = parser.parse_args()
    compute_matches(top_k=args.top_k)
