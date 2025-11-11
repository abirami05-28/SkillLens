# backend/processing/match_jobs.py
import os, sys, argparse
import pymongo
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "skilllens")

if not MONGO_URI:
    print("❌ ERROR: MONGO_URI missing in .env")
    sys.exit(1)

# MongoDB connection
client = pymongo.MongoClient(MONGO_URI)
db = client[MONGO_DB]
candidates = db["candidates"]
jobs = db["jobs"]
matches = db["matches"]

def jaccard(set1, set2):
    """Compute Jaccard similarity between two lists."""
    s1, s2 = set(set1), set(set2)
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / len(s1 | s2)

def precompute_matches(top_k=5):
    """Match each job to top K candidates using embeddings and skill overlap."""
    all_candidates = list(candidates.find({"embedding": {"$exists": True}}))
    print(f"👥 Loaded {len(all_candidates)} candidates with embeddings")

    for job in jobs.find({"embedding": {"$exists": True}}):
        job_emb = np.array(job["embedding"]).reshape(1, -1)
        results = []

        for cand in all_candidates:
            cand_emb = np.array(cand["embedding"]).reshape(1, -1)
            cos_sim = cosine_similarity(job_emb, cand_emb)[0][0]

            # Handle skill overlap safely
            job_skills = job.get("Skills Required", "")
            job_skills = [s.strip() for s in job_skills.split(",")] if job_skills else []
            cand_skills = cand.get("skills", [])

            jac_sim = jaccard(job_skills, cand_skills)

            # Weighted score: 70% embedding, 30% skill overlap
            score = 0.7 * cos_sim + 0.3 * jac_sim

            results.append({
                "candidate_id": str(cand["_id"]),
                "name": cand.get("name"),
                "score": round(float(score), 4)
            })

        # Sort and pick top-K candidates
        results = sorted(results, key=lambda x: x["score"], reverse=True)[:top_k]
        job_id = job.get("job_id") or str(job.get("_id"))
        job_title = job.get("Job Title") or job.get("title") or "Untitled Job"

        # Save results in MongoDB with timestamp
        matches.update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "job_id": job_id,
                    "job_title": job_title,
                    "matches": results,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )

        print(f"✅ Stored {len(results)} matches for job '{job_title}'")

    print("🏁 All job-candidate matches computed and saved.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--top_k", type=int, default=5, help="Number of top candidates per job")
    args = parser.parse_args()
    precompute_matches(top_k=args.top_k)
