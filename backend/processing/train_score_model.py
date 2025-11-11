# backend/processing/train_score_model.py
import os, joblib
import pandas as pd
import numpy as np
import pymongo
from dotenv import load_dotenv
from sklearn.model_selection import train_test_split
from lightgbm import LGBMClassifier
from sklearn.metrics import accuracy_score, roc_auc_score

load_dotenv()
client = pymongo.MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DB","skilllens")]
c = db["candidates"]

docs = list(c.find({"embedding": {"$exists": True}}))
df = pd.DataFrame(docs)

# target variable
df["label"] = df.get("recruiter_decision", "").apply(
    lambda x: 1 if str(x).lower().startswith("hire") or str(x).lower().startswith("short") else 0
)

train_df = df[df["label"].notnull()]
if train_df.shape[0] < 10:
    print("Not enough labeled rows:", train_df.shape[0]); exit(0)

# Features
X_emb = np.vstack(train_df["embedding"].values)  # embeddings
X_num = train_df[["experience","projects_count","ai_score","salary_expectation"]].fillna(0).values
X = np.hstack([X_emb, X_num])   # concat embeddings + numeric

y = train_df["label"].astype(int).values

# Train/test split
X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

# Train LightGBM
model = LGBMClassifier(n_estimators=200, learning_rate=0.05)
model.fit(X_train, y_train)

pred = model.predict(X_val)
print("Accuracy:", accuracy_score(y_val, pred))
if hasattr(model, "predict_proba"):
    print("AUC (approx):", roc_auc_score(y_val, model.predict_proba(X_val)[:,1]))

os.makedirs("models", exist_ok=True)
joblib.dump(model, "models/score_model.pkl")
print("Saved embedding-based model")
