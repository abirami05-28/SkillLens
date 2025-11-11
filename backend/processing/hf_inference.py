# backend/integrations/hf_inference.py
import os
import requests
from dotenv import load_dotenv
from typing import List, Dict, Any

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
HF_API = os.getenv("HF_API_URL", "https://api-inference.huggingface.co/models")

if not HF_TOKEN:
    raise RuntimeError("HF_TOKEN missing in .env")

HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}
TIMEOUT = 30  # seconds, tune if needed

def _call_model(model_id: str, payload: dict) -> dict:
    url = f"{HF_API}/{model_id}"
    resp = requests.post(url, headers=HEADERS, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()

# ---- NER ----
def ner(text: str, model: str = "dbmdz/bert-large-cased-finetuned-conll03-english") -> List[Dict[str, Any]]:
    """
    Call HF inference for token classification (NER).
    Default model: bert model finetuned on CONLL03.
    Returns list of entities: [{'word': .., 'entity': 'B-PER', 'score': 0.99, 'start':.., 'end':..}, ...]
    """
    payload = {"inputs": text}
    out = _call_model(model, payload)
    # Out format may be: [{'entity': 'I-PER', 'score': 0.99, 'index': 1, 'word': 'John'}...]
    return out

# ---- Embeddings ----
def embed(texts: List[str], model: str = "sentence-transformers/all-MiniLM-L6-v2") -> List[List[float]]:
    """
    Request embeddings for a list of texts.
    Some HF models provide 'embedding' or 'vector'. For the inference API, use a model that supports feature-extraction.
    Note: not all models expose embeddings via the inference API; if embedding model is not available use local SBERT.
    """
    # Try feature-extraction endpoint first
    if len(texts) == 1:
        payload = {"inputs": texts[0]}
        out = _call_model(model, payload)
        # out might be nested lists of token embeddings; average them if necessary
        # Many models return token-level embeddings; for sentence embedding we average tokens
        if isinstance(out, list) and all(isinstance(x, list) for x in out):
            # average token vectors
            import numpy as np
            vec = np.mean(out, axis=0).tolist()
            return [vec]
        # If out directly contains a vector
        if isinstance(out, dict) and "embedding" in out:
            return [out["embedding"]]
        return [out]
    else:
        results = []
        for t in texts:
            results.extend(embed([t], model=model))
        return results
