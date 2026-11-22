from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

BEHAVIOURAL_COLUMNS = [
    "amount", "is_new_recipient", "recent_suspicious_sms",
    "recent_suspicious_call", "credential_request_detected", "new_device"
]


def build_behaviour_model(random_state: int = 42) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=200,
        class_weight="balanced",
        random_state=random_state,
    )


def build_anomaly_model(random_state: int = 42) -> Pipeline:
    return Pipeline([
        ("scale", StandardScaler()),
        ("isolation", IsolationForest(
            contamination="auto",
            random_state=random_state,
        )),
    ])
