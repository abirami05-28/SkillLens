# backend/processing/process_jobs.py
import os, sys, argparse
import pymongo
from dotenv import load_dotenv
from processing.embedder import text_to_embedding

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "skilllens")

if not MONGO_URI:
    print("❌ MONGO_URI missing in .env")
    sys.exit(1)

# MongoDB connection
client = pymongo.MongoClient(MONGO_URI)
db = client[MONGO_DB]
jobs = db["jobs"]

def build_text_for_job(job_doc):
    """Combine job fields into one text blob for embeddings."""
    key_variants = {
        "title": ["title", "Job Title"],
        "skills": ["skills", "Skills Required"],
        "description": ["description", "Job Description"],
        "certifications": ["certifications", "Certifications Preferred"],
        "education": ["education", "Education Requirement"],
    }

    parts = []
    for _, variants in key_variants.items():
        for key in variants:
            if key in job_doc:
                value = job_doc.get(key)
                if value:
                    if isinstance(value, list):
                        parts.extend(value)
                    else:
                        parts.append(str(value))
                break  # stop after the first valid match for this field

    return " ".join(parts).strip()

def process(limit=None):
    """Generate embeddings for job documents and store them in MongoDB."""
    cursor = jobs.find({})
    count = 0

    for job in cursor:
        try:
            text = build_text_for_job(job)
            
            # 🛑 Skip jobs that have no usable text
            if not text:
                print(f"⚠️ Skipping job {job.get('_id')} - no content for embedding")
                continue

            # Generate embedding
            emb = text_to_embedding(text)

            # Save to DB
            jobs.update_one({"_id": job["_id"]}, {"$set": {"embedding": emb}})
            count += 1

            if limit and count >= limit:
                break

            if count % 50 == 0:
                print(f"✅ Processed {count} job records")

        except Exception as e:
            print(f"❌ Error processing job {job.get('_id')}: {e}")

    print(f"🏁 Done. Total jobs processed: {count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Limit number of jobs to process")
    args = parser.parse_args()
    process(limit=args.limit)
