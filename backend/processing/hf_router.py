# backend/processing/hf_router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import torch
import numpy as np

router = APIRouter(prefix="/hf", tags=["sbert"])

# 🔹 Load model once on startup
MODEL_NAME = "all-MiniLM-L6-v2"
print(f"🔹 Loading local SBERT model: {MODEL_NAME} ...")
try:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(MODEL_NAME, device=device)
    print(f"✅ Model loaded successfully on {device.upper()}")
except Exception as e:
    print(f"❌ Failed to load model: {e}")
    model = None


class EmbedRequest(BaseModel):
    text: str


@router.post("/embed")
async def embed_text(payload: EmbedRequest):
    """API route: /hf/embed"""
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Missing 'text'")

    try:
        vec = model.encode([text], normalize_embeddings=True)[0]
        return {"embedding": vec.tolist()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {e}")


# ✅ Core reusable embedding function (for backend logic)
async def embed_text_direct(text: str):
    """Direct embedding function (no HTTP) used in backend."""
    if model is None:
        print("⚠️ SBERT model not loaded — returning empty embedding.")
        return []

    text = text.strip()
    if not text:
        return []

    try:
        vec = model.encode([text], normalize_embeddings=True)[0]
        return vec.tolist()
    except Exception as e:
        print(f"Embedding generation failed for text: {e}")
        return []
