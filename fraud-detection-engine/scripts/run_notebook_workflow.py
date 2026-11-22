import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = [
    "01-EDA.ipynb",
    "02_preprocessing_feature_engineering.ipynb",
    "03_sms_communication_fraud.ipynb",
    "04_paysim_transaction_fraud.ipynb",
    "05_behavioural_fraud.ipynb",
    "06_event_correlation_risk.ipynb",
    "07_integrated_testing_evaluation.ipynb",
]


for filename in NOTEBOOKS:
    notebook = PROJECT_ROOT / "notebooks" / filename
    print(f"Executing {filename}...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "jupyter",
            "nbconvert",
            "--to",
            "notebook",
            "--execute",
            "--inplace",
            "--ExecutePreprocessor.timeout=600",
            "--ExecutePreprocessor.kernel_name=python3",
            str(notebook),
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )

print("Notebook workflow completed successfully.")
