"""Train TF-IDF and transformer text models from independently labeled messages."""

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import joblib
import pandas as pd
from sklearn.metrics import average_precision_score

from momo_fraud.models.text_clf import make_text_baseline
from momo_fraud.models.text_transformer import train_text_transformer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/raw/text_labels.csv")
    parser.add_argument("--output-dir", default="models/text")
    parser.add_argument("--model-name", default="Davlan/afro-xlmr-base")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        raise FileNotFoundError(
            f"Labeled text file not found: {input_path}. Do not derive text labels "
            "from the same synthetic fraud scenario being evaluated."
        )
    data = pd.read_csv(input_path)
    required = {"text", "is_fraud", "split"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(
            "Text labels are missing columns: " + ", ".join(sorted(missing))
        )
    data = data.dropna(subset=["text", "is_fraud", "split"])
    if "fraud_case" in data:
        split_counts = data.groupby("fraud_case")["split"].nunique()
        if (split_counts > 1).any():
            raise ValueError("A fraud_case appears in multiple text-data splits.")

    train = data.loc[data["split"] == "train"]
    validation = data.loc[data["split"] == "validation"]
    if train.empty or validation.empty:
        raise ValueError("Text data must include train and validation rows.")
    if set(train["is_fraud"].astype(int).unique()) != {0, 1}:
        raise ValueError("Training text labels must contain both classes 0 and 1.")
    if set(validation["is_fraud"].astype(int).unique()) != {0, 1}:
        raise ValueError("Validation text labels must contain both classes 0 and 1.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    text_model = make_text_baseline()
    text_model.fit(train["text"].astype(str), train["is_fraud"].astype(int))
    tfidf_probability = text_model.predict_proba(validation["text"].astype(str))[:, 1]
    joblib.dump(text_model, output_dir / "tfidf_text.joblib")

    transformer_report = train_text_transformer(
        train["text"].astype(str).tolist(),
        train["is_fraud"].astype(int).tolist(),
        validation["text"].astype(str).tolist(),
        validation["is_fraud"].astype(int).tolist(),
        output_dir=output_dir / "transformer",
        model_name=args.model_name,
    )
    report = {
        "text_rows": {"train": len(train), "validation": len(validation)},
        "tfidf_validation_pr_auc": float(
            average_precision_score(
                validation["is_fraud"].astype(int), tfidf_probability
            )
        ),
        "transformer": transformer_report,
        "warning": "Validation is for development only; keep a separate blind test set.",
    }
    report_path = output_dir / "text_metrics.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
