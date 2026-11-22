from pathlib import Path
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from src.preprocessing import clean_text
from src.features import detect_behaviours


def build_sms_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            preprocessor=clean_text,
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
        )),
        ("classifier", LogisticRegression(class_weight="balanced", max_iter=1000)),
    ])


def analyse_message(event_id: str, message: str, model=None) -> dict:
    behaviours = detect_behaviours(message)
    probability = 0.0
    if model is not None:
        probability = float(model.predict_proba([message])[0, 1])
    classification = "SUSPICIOUS" if probability >= 0.5 or len(behaviours) >= 2 else "LEGITIMATE"
    return {
        "event_id": event_id,
        "fraud_probability": round(probability, 4),
        "detected_behaviours": behaviours,
        "classification": classification,
    }


def save_model(model, path: str | Path) -> None:
    joblib.dump(model, Path(path))


def load_model(path: str | Path):
    return joblib.load(Path(path))
