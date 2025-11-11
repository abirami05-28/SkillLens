from fastapi import FastAPI, File, UploadFile, HTTPException, Depends 
from fastapi.middleware.cors import CORSMiddleware 
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import pandas as pd
import io
from bson import ObjectId
from datetime import datetime 
import bcrypt, jwt
from datetime import datetime, timedelta
from auth.routes import auth_router
from processing import hf_router 
from db import mongo
import math
import os
from calendar_api.routes import calendar_router
from dotenv import load_dotenv
from resume.routes import router as resume_router 
from analytics import skill_rules, cluster_candidates, fairness_eval, bias_summary
from processing.similarity import cosine_similarity, jaccard_similarity
from processing.hf_router import embed_text, embed_text_direct
from processing.normalize import get_field
from bson import ObjectId
import numpy as np

app = FastAPI()
def safe_float(x):
    try:
        return float(x)
    except:
        return 0.0
def safe_int(x):
    try:
        return int(float(x))
    except:
        return 0

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(calendar_router) 
app.include_router(hf_router.router) 
app.include_router(resume_router, prefix="/resume", tags=["Resume"])
load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET", "replace_this_in_env")

print("DEBUG: HF_API_KEY =", os.getenv("HF_API_KEY"))
# Allow all origins for now (safe in dev, restrict in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://localhost:3000"] for your frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define what input looks like
class Candidate(BaseModel):
    name: str
    skills: list[str]

class SignupSchema(BaseModel):
    username: str
    email: EmailStr
    password: str

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

@app.get("/")
async def root():
    return {"msg": "SkillLens backend running"}

bearer_scheme = HTTPBearer()

def verify_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/auth/me")
async def get_me(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    payload = verify_token(token)

    db = mongo.get_database()
    if db is None:
        await mongo.init_mongo()
        db = mongo.get_database()

    user = await db["users"].find_one({"email": payload.get("email")})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user["_id"] = str(user["_id"])
    return {
        "user": {
            "id": user["_id"],
            "username": user.get("username"),
            "email": user.get("email"),
            "orgname": user.get("orgname") or "",
            "contact": user.get("contact") or "",
            "address": user.get("address") or "",
        }
    }
from fastapi import Body

@app.put("/auth/update_profile")
async def update_profile(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    payload: dict = Body(...)
):
    token = credentials.credentials
    user_data = verify_token(token)

    db = mongo.get_database()
    if db is None:
        await mongo.init_mongo()
        db = mongo.get_database()

    user = await db["users"].find_one({"email": user_data["email"]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_fields = {}
    for key in ["orgname", "contact", "address"]:
        if payload.get(key) is not None:
            update_fields[key] = payload[key]

    if not update_fields:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    await db["users"].update_one(
        {"_id": user["_id"]},
        {"$set": update_fields}
    )

    return {"msg": "Profile updated successfully", "updated_fields": update_fields}

@app.post("/add_candidate")
async def add_candidate(candidate: Candidate):
    doc = candidate.dict()
    result = await mongo.candidates_collection.insert_one(doc)
    return {"inserted_id": str(result.inserted_id)}

@app.get("/candidates")
async def get_candidates():
    # Ensure DB is connected
    if mongo.candidates_collection is None:
        await mongo.init_mongo()

    def sanitize_value(v):
        if isinstance(v, float):
            if v != v or v in (float("inf"), float("-inf")):
                return None
            return v
        if isinstance(v, dict):
            return {k: sanitize_value(val) for k, val in v.items()}
        if isinstance(v, list):
            return [sanitize_value(i) for i in v]
        return v

    candidates = []
    async for c in mongo.candidates_collection.find():
        c["_id"] = str(c["_id"])
        c = sanitize_value(c)
        candidates.append(c)

    return {"candidates": candidates}

@app.post("/upload_csv")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    try:
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode("utf-8")))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading CSV: {e}")

    records = []
    for _, row in df.iterrows():
        candidate = {
            "resume_id": row.get("Resume_ID"),
            "name": row.get("Name"),
            "skills": [s.strip() for s in str(row.get("Skills") or "").split(",") if s.strip()],
            "experience": safe_float(row.get("Experience (Years)")),
            "education": row.get("Education"),
            "certifications": row.get("Certifications"),
            "job_role": row.get("Job Role"),
            "recruiter_decision": row.get("Recruiter Decision"),
            "salary_expectation": safe_float(row.get("Salary Expectation ($)")),
            "projects_count": safe_int(row.get("Projects Count")),
            "ai_score": safe_float(row.get("AI Score (0-100)")),
            "gender": row.get("Gender"),
            "age": row.get("Age"),
        }
            # Build unified text field for embedding
        candidate_text = f"{row.get('Name', '')} {row.get('Job Role', '')} {row.get('Skills', '')} {row.get('Education', '')}"
        candidate["text"] = candidate_text.strip()
        candidate["source"] = "csv"
        records.append(candidate)

    try:
        result = await mongo.candidates_collection.insert_many(records)
        return {"inserted_count": len(result.inserted_ids)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error inserting records: {e}")

@app.post("/upload_jobs_csv")
async def upload_jobs_csv(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV allowed")

    try:
        df = pd.read_csv(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {e}")

    from processing.hf_router import embed_text_direct

    jobs = []
    for _, row in df.iterrows():
        job_id = str(row.get("Job ID") or f"job_{_+1}")
        title = row.get("Job Title")
        desc = row.get("Job Description", "")
        skills = [s.strip() for s in str(row.get("Skills Required") or "").split(",") if s.strip()]

        # ✅ Build text for embedding
        job_text = f"{title or ''}. {desc or ''}. Skills: {', '.join(skills)}"

        # ✅ Generate embedding immediately
        embedding = await embed_text_direct(job_text)

        job = {
            "job_id": job_id,
            "title": title,
            "skills": skills,
            "experience_required": float(row.get("Experience Required (Years)") or 0),
            "education": row.get("Education Requirement"),
            "certifications": row.get("Certifications Preferred"),
            "description": desc,
            "salary_offered": float(row.get("Salary Offered") or 0),
            "projects_expected": int(row.get("Projects Expected") or 0),
            "embedding": embedding if embedding else []
        }

        jobs.append(job)

    result = await mongo.datab.get_collection("jobs").insert_many(jobs)
    return {
        "inserted_count": len(result.inserted_ids),
        "embedded_jobs": sum(1 for j in jobs if j["embedding"]),
    }



@app.get("/match_job/{job_id}")
async def match_job(job_id: str, top_k: int = 10):
    jobs_coll = mongo.datab.get_collection("jobs")
    cand_coll = mongo.datab.get_collection("candidates")

    job = await jobs_coll.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job_title = get_field(job, ["title", "job_title", "Job Title"])
    job_desc = get_field(job, ["description", "job_description", "Description"])
    job_skills = get_field(job, ["skills", "Skills Required", "technical_skills", "Skill Set"], [])

    if isinstance(job_skills, str):
        job_skills = [s.strip() for s in job_skills.split(",") if s.strip()]

    # generate job embedding if missing (and normalize)
    if "embedding" not in job or not job.get("embedding"):
        job_text = f"{job_title or ''} {job_desc or ''}"
        job_emb = await embed_text(job_text)
        # embed_text might return {"embedding": [...]} or list; normalize:
        if isinstance(job_emb, dict) and "embedding" in job_emb:
            job_emb = job_emb["embedding"]
        # ensure it's JSON-serializable (list) before saving
        try:
            # convert numpy arrays to lists if returned
            import numpy as _np
            if isinstance(job_emb, _np.ndarray):
                job_emb = job_emb.tolist()
        except Exception:
            pass
        await jobs_coll.update_one({"_id": job["_id"]}, {"$set": {"embedding": job_emb}})
        job["embedding"] = job_emb

    # helper to normalize embedding shapes (list, tuple, np.ndarray, or dict)
    def ensure_array(emb):
        import numpy as _np
        if emb is None:
            return None
        if isinstance(emb, dict):
            # if embedding stored as dict like {"0":..., "1":...} or {"embedding": [...]}
            if "embedding" in emb:
                emb = emb["embedding"]
            else:
                # fallback: take dict values in key order
                try:
                    return _np.array([v for k, v in sorted(emb.items(), key=lambda x: int(x[0]))])
                except Exception:
                    return _np.array(list(emb.values()))
        if isinstance(emb, _np.ndarray):
            return emb
        return _np.array(emb)

    results = []
    cursor = cand_coll.find({"embedding": {"$exists": True}})
    async for c in cursor:
        cand_skills = get_field(c, ["skills", "technical_skills", "Skill Set"], [])
        if isinstance(cand_skills, str):
            cand_skills = [s.strip() for s in cand_skills.split(",") if s.strip()]

        job_emb_arr = ensure_array(job.get("embedding"))
        cand_emb_arr = ensure_array(c.get("embedding"))
        if job_emb_arr is None or cand_emb_arr is None:
            # skip if embedding missing or invalid
            continue

        cos = float(cosine_similarity(job_emb_arr, cand_emb_arr))
        jacc = float(jaccard_similarity(job_skills, cand_skills))
        score = 0.75 * cos + 0.25 * jacc

        # ✅ Store the score in the candidate document for analytics use
        await cand_coll.update_one(
            {"_id": c["_id"]},
            {"$set": {"model_score": score}}
        )

        results.append({
            "candidate_id": str(c["_id"]),
            "name": get_field(c, ["name", "full_name", "candidate_name"]),
            "skills": cand_skills,
            "recruiter_decision": c.get("recruiter_decision"),
            "cosine": cos,
            "jaccard": jacc,
            "score": score
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return {"job_id": job_id, "top_k": results[:top_k]}

@app.get("/matches/{job_id}")
async def get_precomputed_matches(job_id: str, top_k: int = 10):
    doc = await mongo.datab.get_collection("matches").find_one({"job_id": job_id})
    if not doc:
        raise HTTPException(status_code=404, detail="No matches found")
    return {"job_id": job_id, "matches": doc["matches"][:top_k]}

@app.get("/candidates/search")
async def search_candidates(skill: str = None, min_experience: float = None, min_score: float = None, limit: int = 50):
    query = {}
    if skill:
        query["skills"] = {"$regex": skill, "$options": "i"}
    if min_experience is not None:
        # support both "parsed_experience" and "experience" fields
        query["$or"] = [
            {"parsed_experience": {"$gte": min_experience}},
            {"experience": {"$gte": min_experience}}
        ]

    if min_score is not None:
        query["model_score"] = {"$gte": min_score}

    docs = []
    cursor = mongo.datab.get_collection("candidates").find(query).limit(limit)
    async for d in cursor:
        d["_id"] = str(d["_id"])
        docs.append(d)
    return {"count": len(docs), "candidates": docs}

from bson import ObjectId

@app.post("/update_decision/{candidate_id}")
async def update_decision(candidate_id: str, payload: dict):
    # ✅ Match frontend terms exactly
    valid_decisions = {"shortlisted", "shortlist", "rejected", "reject", "hired", "hire"}
    decision = payload.get("recruiter_decision") or payload.get("decision")
    if decision:
        decision = decision.lower().strip()
        if decision in ["hire", "reject", "shortlist"]:
            decision += "ed"


    # ✅ Support both 'decision' and 'recruiter_decision' keys from frontend
    decision = payload.get("recruiter_decision") or payload.get("decision")

    if not decision or decision not in valid_decisions:
        raise HTTPException(status_code=400, detail=f"Invalid decision. Allowed: {sorted(valid_decisions)}")

    db = mongo.datab
    if db is None:
        raise HTTPException(status_code=500, detail="MongoDB not initialized")

    # ✅ Handle both ObjectId and UUIDs for _id
    query = {"_id": candidate_id}
    try:
        query = {"_id": ObjectId(candidate_id)}
    except Exception:
        pass

    result = await db.get_collection("candidates").update_one(
        query,
        {"$set": {"recruiter_decision": decision, "updated_at": datetime.utcnow()}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return {"msg": f"Decision '{decision}' recorded for candidate {candidate_id}"}

@app.get("/analytics/skills")
async def get_skill_rules(limit: int = 20):
    doc = await mongo.datab.get_collection("analytics").find_one({"name": "skill_rules"})
    if not doc or "rules" not in doc:
        return {"rules": []}
    return {"rules": doc["rules"][:limit]}

@app.get("/analytics/clusters")
async def get_clusters():
    doc = await mongo.datab.get_collection("analytics").find_one({"name": "clusters"})
    if not doc or "clusters" not in doc:
        return {"clusters": []}

    clusters = [{"cluster": c["cluster"], "count": c["count"]} for c in doc["clusters"]]
    return {"clusters": clusters}

@app.get("/analytics/bias/{attribute}")
async def get_bias(attribute: str, source: str = "summary"):
    coll_name = "bias_metrics" if source == "summary" else "fairness_eval"
    doc = await mongo.datab.get_collection(coll_name).find_one({"attribute": attribute})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No {source} bias metrics found for {attribute}")

    doc["_id"] = str(doc["_id"])

    def sanitize(v):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        if isinstance(v, dict):
            return {k: sanitize(val) for k, val in v.items()}
        return v

    doc = {k: sanitize(v) for k, v in doc.items()}
    return doc

@app.get("/analytics/funnel")
async def get_funnel():
    cand_coll = mongo.datab.get_collection("candidates")
    total = await cand_coll.count_documents({})
    screened = await cand_coll.count_documents({"recruiter_decision": {"$ne": None}})
    shortlisted = await cand_coll.count_documents({"recruiter_decision": "shortlisted"})
    hired = await cand_coll.count_documents({"recruiter_decision": "hired"})

    return {
        "total": total,
        "screened": screened,
        "shortlisted": shortlisted,
        "hired": hired
    }

@app.post("/analytics/recompute/skills")
async def recompute_skills():
    return skill_rules.run()

@app.post("/analytics/recompute/clusters")
async def recompute_clusters():
    return cluster_candidates.run()

@app.post("/analytics/recompute/fairness")
async def recompute_fairness():
    return fairness_eval.run()

@app.post("/analytics/recompute/bias_summary")
async def recompute_bias_summary():
    return bias_summary.run()

@app.post("/auth/signup")
async def signup(user: SignupSchema):
    existing = await mongo.users_collection.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    hashed_pw = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt())

    doc = {
        "username": user.username,
        "email": user.email,
        "password": hashed_pw.decode("utf-8"),
        "orgname": getattr(user, "orgname", ""),
        "contact": getattr(user, "contact", ""),
        "address": getattr(user, "address", ""),
        "createdAt": datetime.utcnow()
    }

    await mongo.users_collection.insert_one(doc)
    return {"msg": "User created successfully"}

@app.post("/auth/login")
async def login(data: LoginSchema):
    user = await mongo.users_collection.find_one({"email": data.email})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    if not bcrypt.checkpw(data.password.encode("utf-8"), user["password"].encode("utf-8")):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    payload = {
        "sub": str(user["_id"]),
        "email": user["email"],
        "username": user.get("username") or user["email"].split("@")[0],  # ✅ Add username here
        "exp": datetime.utcnow() + timedelta(hours=1)
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}

import asyncio
@app.get("/test_mongo")
async def test_mongo():
    db = mongo.get_database()
    if db is None:
        return {"status": "Mongo not initialized"}
    try:
        col = db["candidates"]
        count = await col.count_documents({})
        return {"status": "connected", "candidates_in_db": count}
    except Exception as e:
        return {"status": "error", "details": str(e)}



async def _maybe_async_call(func, *args, **kwargs):
    """
    Call func(*args, **kwargs).
    ``it returns a coroutine, await it.
    If it is synchronous, run it in a thread via asyncio.to_thread.
    Returns the function's return value.
    """
    try:
        result = func(*args, **kwargs)
    except Exception as e:
        # If calling raises synchronously, re-raise to be handled by caller
        raise

    if asyncio.iscoroutine(result):
        return await result
    # run synchronous result in thread to avoid blocking event loop
    return await asyncio.to_thread(lambda: result)

# --- recompute helper for all analytics --- 
async def recompute_all_analytics():
    """
    Run all analytics pipelines: skill rules, clusters, fairness, bias summaries.
    This will attempt to call either sync or async run() from each module.
    """
    errors = {}
    try:
        await _maybe_async_call(skill_rules.run)
    except Exception as e:
        errors["skill_rules"] = str(e)

    try:
        await _maybe_async_call(cluster_candidates.run)
    except Exception as e:
        errors["cluster_candidates"] = str(e)

    try:
        await _maybe_async_call(fairness_eval.run)
    except Exception as e:
        errors["fairness_eval"] = str(e)

    try:
        await _maybe_async_call(bias_summary.run)
    except Exception as e:
        errors["bias_summary"] = str(e)

    if errors:
        # Log errors to console (you can expand to proper logging)
        print("Analytics recompute errors:", errors)
        return {"ok": False, "errors": errors}
    print("Analytics recomputed successfully.")
    return {"ok": True}

@app.on_event("startup")
async def startup_event():
    await mongo.init_mongo()

if __name__ == "_main_":
    import asyncio
from processing.hf_router import embed_text_direct

@app.post("/upload_csv_with_embeddings")
async def upload_csv_with_embeddings(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    try:
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode("utf-8")))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading CSV: {e}")

    from processing.hf_router import embed_text_direct

    # ✅ Ensure MongoDB connection
    db = mongo.get_database()
    if db is None:
        await mongo.init_mongo()
        db = mongo.get_database()

    candidates = []
    for _, row in df.iterrows():
        name = row.get("Name", "")
        job_role = row.get("Job Role", "")
        skills = [s.strip() for s in str(row.get("Skills") or "").split(",") if s.strip()]
        education = row.get("Education", "")
        certs = row.get("Certifications", "")

        text = f"{name} {job_role} {' '.join(skills)} {education} {certs}".strip()
        embedding = await embed_text_direct(text)

        candidates.append({
            "name": name,
            "email": row.get("Email", ""),
            "skills": skills,
            "job_role": job_role,
            "education": education,
            "certifications": certs,
            "experience": float(row.get("Experience (Years)") or 0),
            "salary_expectation": float(row.get("Salary Expectation ($)") or 0),
            "projects_count": int(row.get("Projects Count") or 0),
            "ai_score": float(row.get("AI Score (0-100)") or 0),
            "gender": row.get("Gender", ""),
            "age": row.get("Age", ""),
            "embedding": embedding if embedding else [],
            "source": "csv",
            "recruiter_decision": None,
            "created_at": datetime.utcnow()
        })

    # ✅ Safe insert
    result = await db.get_collection("candidates").insert_many(candidates)
    return {
        "msg": "✅ CSV uploaded and candidates inserted successfully!",
        "inserted_count": len(result.inserted_ids)
    }


@app.post("/recompute_job_embeddings")
async def recompute_job_embeddings():
    """
    Recompute and add embeddings for all jobs missing them.
    Run by calling POST /recompute_job_embeddings once.
    """
    db = mongo.get_database()
    if db is None:
        await mongo.init_mongo()
        db = mongo.get_database()

    jobs_coll = db.get_collection("jobs")
    updated = 0

    async for job in jobs_coll.find({"$or": [{"embedding": {"$exists": False}}, {"embedding": []}]}):
        title = job.get("title", "")
        desc = job.get("description", "")
        skills = job.get("skills", [])
        text = f"{title}. {desc}. Skills: {', '.join(skills)}"

        emb = await embed_text_direct(text)
        await jobs_coll.update_one({"_id": job["_id"]}, {"$set": {"embedding": emb}})
        updated += 1

    return {"msg": f"Updated embeddings for {updated} job(s)."}

@app.post("/analytics/recompute_all")
async def recompute_all():
    """Recompute all analytics for the dashboard (safe for sync/async modules)."""
    from analytics import skill_rules, cluster_candidates, fairness_eval, bias_summary
    import asyncio

    async def run_maybe_async(func):
        """Run sync or async analytics function safely."""
        result = func()
        if asyncio.iscoroutine(result):
            return await result
        return result

    try:
        await run_maybe_async(skill_rules.run)
        await run_maybe_async(cluster_candidates.run)
        await run_maybe_async(fairness_eval.run)
        await run_maybe_async(bias_summary.run)
        return {"msg": "✅ All analytics recomputed successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics recompute failed: {e}")