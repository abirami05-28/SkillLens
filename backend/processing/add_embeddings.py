'''import asyncio
from db.mongo import init_mongo, get_database
from processing.hf_router import embed_text  # keep this import
from bson import ObjectId

async def recompute_candidate_embeddings():
    db = await init_mongo()
    if db is None:
        print("❌ MongoDB not initialized properly")
        return

    candidates_collection = db.get_collection("candidates")
    print("✅ MongoDB connection successful")
    print("🧠 Generating embeddings for resumes...")

    cursor = candidates_collection.find({})
    async for cand in cursor:
        text = cand.get("parsed_text") or cand.get("text") or ""
        if not text.strip():
            continue

        embedding = await embed_text(text)
        await candidates_collection.update_one(
            {"_id": cand["_id"]},
            {"$set": {"embedding": embedding}}
        )

    print("✅ Added embeddings for all resumes!")

if __name__ == "__main__":
    asyncio.run(recompute_candidate_embeddings())
'''
# backend/add_embeddings.py
import asyncio
from db.mongo import init_mongo, get_database
from processing.hf_router import embed_text_direct
from bson import ObjectId

async def recompute_candidate_embeddings():
    db = await init_mongo()
    if db is None:
        print("❌ MongoDB not initialized properly")
        return

    candidates_collection = db.get_collection("candidates")
    print("✅ MongoDB connection successful")
    print("🧠 Generating embeddings for resumes...")

    cursor = candidates_collection.find({})
    count = 0

    async for cand in cursor:
        text_parts = [
            str(cand.get("name", "")),
            " ".join(cand.get("skills", [])) if isinstance(cand.get("skills"), list) else str(cand.get("skills", "")),
            str(cand.get("education", "")),
            str(cand.get("certifications", "")),
            str(cand.get("job_role", "")),
            str(cand.get("experience", "")),
            str(cand.get("projects_count", "")),
            str(cand.get("recruiter_decision", "")),
            cand.get("text", ""),
        ]
        text = " ".join([t for t in text_parts if t.strip()])

        if not text.strip():
            continue

        embedding = await embed_text_direct(text)
        await candidates_collection.update_one(
            {"_id": cand["_id"]},
            {"$set": {"embedding": embedding}}
        )
        count += 1
        if count % 10 == 0:
            print(f"🟦 Processed {count} resumes...")

    print(f"✅ Added embeddings for all resumes ({count} total).")

if __name__ == "__main__":
    asyncio.run(recompute_candidate_embeddings())
