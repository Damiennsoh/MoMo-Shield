# 3nSendi Fraud Detection Prototype

This workspace implements a six-stage prototype for detecting mobile-money social engineering and correlating communication with transactions.

## Structure

- `notebooks/01` through `notebooks/07`: sequential EDA, preprocessing, detection, correlation, and evaluation workflow.
- `src/`: reusable preprocessing, detection, correlation, risk, and explanation modules.
- `data/synthetic/`: canonical combined communication, transaction, and integrated test datasets.
- `data/raw/`: local PaySim CSV, downloaded separately; raw data is not included in this repository.
- `data/processed/`: processed outputs and saved models.
- `tests/`: focused unit tests.

## Canonical datasets

- `data/synthetic/communication_events.csv`: merged scripted communication records for text classification; retains source records, `scenario_tags`, origin, and label columns.
- `data/synthetic/transactions.csv`: merged scripted transaction/behaviour records for behavioural classification; retains transaction types and credential, device, and reported-recipient fields where available.
- `data/synthetic/integrated_event_test.csv`: small event-sequence fixture for end-to-end scenario checks, not model training.
- PaySim version 2 is not included because its raw CSV exceeds GitHub's file-size limit. Download it from [Kaggle](https://www.kaggle.com/datasets/ealaxi/paysim1), extract `PS_20174392719_1491204439457_log.csv` into `data/raw/`, and retain its CC BY-SA 4.0 attribution if redistributing derived work. Keep it separate from scripted datasets because it has different labels and features.

The unrelated UCI general SMS-spam dataset was removed; its spam/ham labels are not mobile-money fraud labels.

## Setup

```powershell
python -m pip install -r requirements.txt
python -m ipykernel install --user --name 3nsendi
pytest -q
```

Open the notebooks sequentially from `01-EDA.ipynb` through `07_integrated_testing_evaluation.ipynb`.

## Notebook execution

Run the complete workflow smoke test from the project root:

```powershell
python scripts/run_notebook_workflow.py
```

The workflow executes all notebooks 01–07, reads the canonical combined synthetic datasets, evaluates synthetic behavioral data and PaySim in separate models, executes correlation and risk scenarios, and saves outputs back into each notebook. Download the PaySim CSV as described above before running the complete workflow; notebooks 01 and 04 require it.

The merged synthetic files preserve source IDs, dataset provenance, labels, and communication scenario tags. They remain scripted test data, not evidence of performance on real-world MoMo fraud.

PaySim is a separate synthetic mobile-money transaction dataset from [Kaggle](https://www.kaggle.com/datasets/ealaxi/paysim1), licensed CC BY-SA 4.0. Retain attribution and the license when redistributing or publishing derived work. PaySim is not real customer data and its fraud labels describe simulator scenarios, not MoMo social-engineering labels.
