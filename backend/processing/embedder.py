# backend/processing/embedder.py
from sentence_transformers import SentenceTransformer
import numpy as np

# Use small, fast SBERT model
MODEL_NAME = "all-MiniLM-L6-v2"
model = SentenceTransformer(MODEL_NAME)

def text_to_embedding(text):
    """
    returns a python list (float) that can be stored in MongoDB
    """
    vec = model.encode([text], show_progress_bar=False)[0]
    return vec.tolist()

def cosine_sim_from_vectors(v1, v2):
    v1 = np.array(v1)
    v2 = np.array(v2)
    if v1.any() and v2.any():
        num = float(np.dot(v1, v2))
        denom = float((np.linalg.norm(v1) * np.linalg.norm(v2)) + 1e-9)
        return num/denom
    return 0.0
print("done")