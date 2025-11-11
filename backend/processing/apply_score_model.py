# backend/processing/apply_score_model.py
import os, joblib, pymongo
import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
client = pymongo.MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DB", "skilllens")]
c = db["candidates"]

# Load trained model
model = joblib.load("models/score_model.pkl")

# Figure out embedding size (from one candidate)
sample_doc = c.find_one({"embedding": {"$exists": True}})
if not sample_doc:
    print("No candidates with embeddings found!")
    exit(0)

embedding_size = len(sample_doc["embedding"])

# Build feature names consistent with training
feature_names = [f"emb_{i}" for i in range(embedding_size)] + [
    "experience", "projects_count", "ai_score", "salary_expectation"
]

docs = list(c.find({"embedding": {"$exists": True}}))
for doc in docs:
    try:
        X_emb = np.array(doc["embedding"]).reshape(1, -1)
        X_num = np.array([[doc.get("experience") or 0,
                           doc.get("projects_count") or 0,
                           doc.get("ai_score") or 0,
                           doc.get("salary_expectation") or 0]])
        X = np.hstack([X_emb, X_num])

        # Create DataFrame with correct column names
        X_df = pd.DataFrame(X, columns=feature_names)

        # Predict
        score = float(model.predict_proba(X_df)[:, 1][0]) if hasattr(model, "predict_proba") else float(model.predict(X_df)[0])

        # Update candidate with score
        c.update_one({"_id": doc["_id"]}, {"$set": {"model_score": score}})
    except Exception as e:
        print("Error scoring doc", doc.get("_id"), str(e))

print("✅ Done applying embedding-based scores to candidates")
