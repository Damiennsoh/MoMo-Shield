"""Build features, run the mock/research experiment, or print saved metrics."""

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from momo_fraud.features.state import build_features
from momo_fraud.io import load_tables, load_yaml_config
from momo_fraud.pipeline import run_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("features", "experiment", "evaluate"))
    parser.add_argument("--data-dir", default=str(PROJECT_ROOT / "data" / "mock_full"))
    parser.add_argument(
        "--columns-config", default=str(PROJECT_ROOT / "configs" / "columns.yaml")
    )
    args = parser.parse_args()

    if args.command == "evaluate":
        report_path = PROJECT_ROOT / "reports" / "metrics" / "latest.json"
        if not report_path.is_file():
            raise FileNotFoundError(
                f"No saved experiment report found at {report_path}; run make train first."
            )
        print(report_path.read_text(encoding="utf-8"))
        return

    tables = load_tables(args.data_dir, args.columns_config)
    feature_config = load_yaml_config(PROJECT_ROOT / "configs" / "features.yaml")
    if args.command == "features":
        features = build_features(tables, config=feature_config)
        output_path = PROJECT_ROOT / "data" / "processed" / "transaction_features.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        features.to_csv(output_path, index=False)
        print(f"Wrote {len(features):,} point-in-time rows to {output_path}")
        return

    result = run_experiment(
        tables,
        model_dir=PROJECT_ROOT / "models",
        report_dir=PROJECT_ROOT / "reports" / "metrics",
        processed_dir=PROJECT_ROOT / "data" / "processed",
        decision_config=PROJECT_ROOT / "configs" / "decision.yaml",
        feature_config=PROJECT_ROOT / "configs" / "features.yaml",
    )
    print(json.dumps(result["report"], indent=2, default=str))


if __name__ == "__main__":
    main()
