# backend/processing/similarity.py
import numpy as np

def cosine_similarity(v1, v2):
    if not isinstance(v1, (list, np.ndarray)) or not isinstance(v2, (list, np.ndarray)):
        return 0.0
    v1 = np.array(v1)
    v2 = np.array(v2)
    if v1.size == 0 or v2.size == 0:
        return 0.0
    denom = (np.linalg.norm(v1) * np.linalg.norm(v2)) + 1e-9
    return float(np.dot(v1, v2) / denom)

def jaccard_similarity(list1, list2):
    if not list1 or not list2:
        return 0.0
    set1 = set([str(s).strip().lower() for s in list1 if s])
    set2 = set([str(s).strip().lower() for s in list2 if s])
    if not set1 and not set2:
        return 0.0
    inter = set1.intersection(set2)
    union = set1.union(set2)
    return float(len(inter) / len(union))
