import lightgbm as lgb
import numpy as np
from sklearn.model_selection import train_test_split

model = None

def train_lightgbm(candidates, jobs):
    """
    Train LightGBM model to predict candidate-job suitability score.
    candidates: list of candidate dicts with 'skills', 'experience', 'ai_score'
    jobs: list of job dicts (optional for now)
    """
    global model

    # Simple feature example: we use ai_score, experience, and similarity
    X, y = [], []
    for c in candidates:
        features = [
            c.get("ai_score", 0),
            c.get("experience", 0),
            len(c.get("skills", []))
        ]
        X.append(features)
        # Use model_score as pseudo-label for now
        y.append(c.get("model_score", 0))

    if not X or not y:
        print("No training data found.")
        return None

    X_train, X_val, y_train, y_val = train_test_split(np.array(X), np.array(y), test_size=0.2, random_state=42)
    train_data = lgb.Dataset(X_train, label=y_train)
    val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

    params = {"objective": "regression", "metric": "rmse", "verbosity": -1}
    model = lgb.train(params, train_data, valid_sets=[val_data], num_boost_round=50, early_stopping_rounds=10)
    print("✅ LightGBM model trained.")
    return model


def predict_lightgbm(features):
    """Predict suitability score given a candidate feature vector."""
    if model is None:
        print("⚠️ Model not trained, returning default score.")
        return 0
    return float(model.predict([features])[0])
