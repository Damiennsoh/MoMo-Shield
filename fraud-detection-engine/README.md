# MoMo Fraud

Point-in-time mobile-money fraud detection rehearsal pipeline.

## Setup

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-advanced.txt
```

The advanced requirements add PyTorch, Transformers, and SentencePiece for
optional graph/text experiments. Real sandbox data is downloaded into
`data/raw/`; map source columns in `configs/columns.yaml`. Copy `.env.example`
to `.env`, set `TEAM` and `TEAM_KEY`, and never commit `.env` or the team key.
The `.env` file is git-ignored.

## Notebook workflow

Run the numbered notebooks in order:

1. [`01_eda.ipynb`](notebooks/01_eda.ipynb) — inspect tables, labels, amounts,
   and synthetic artifacts.
2. [`02_leakage_audit.ipynb`](notebooks/02_leakage_audit.ipynb) — replay
   point-in-time features and check time/case splits.
3. [`03_feature_importance.ipynb`](notebooks/03_feature_importance.ipynb) —
   fit the tabular ensemble, inspect SHAP, compare an experimental GNN, and
   fine-tune a transformer only if independent text labels are available.
4. [`04_error_analysis.ipynb`](notebooks/04_error_analysis.ipynb) — review
   missed fraud, false alerts, calibration, expected-cost actions, latency, and
   the Twi review gate.

The notebooks prefer `data/raw/` for real sandbox downloads and fall back to
`data/mock_full/` only when real data is not present. Synthetic results are for
rehearsal only and must not be reported as real-world performance.

## Command-line run

```powershell
python scripts/fetch_and_profile.py --simulate
python scripts/mock_sandbox.py --people 4000 --tx 78018 --cases 8720 --seed 7 --total-transactions 100023 --fraud-fraction 0.22 --out data/mock_full
python scripts/run_pipeline.py experiment --data-dir data/mock_full
python -m pytest -q
```

`make data` simulates and downloads the live sandbox world into `data/raw/`,
then profiles all available CSV tables. `make mock-data`, `make features`,
`make train`,
`make evaluate`, `make serve`, and `make train-text` provide shortcuts.
`make train` runs training, validation calibration, test evaluation, and an
in-process single-row latency benchmark. `make evaluate` prints the latest
saved report.

## Implemented pipeline

- One timestamp-ordered replay creates transactional velocity, new-payee,
  near-limit, recipient graph aggregates, call, keyword/message-ledger, SIM/PIN,
  and wallet-age features using strictly earlier events. Fraud labels and case
  metadata are excluded from model features.
- Cases crossing chronological split boundaries are excluded.
- Rules, class-weighted logistic regression, LightGBM, Isolation Forest anomaly
  scores, and a validation-calibrated probability blend are evaluated. SHAP
  explanations are available for the boosted-tree component.
- Expected loss (`probability * amount`) maps to allow/warn/hold/freeze actions
  using `configs/decision.yaml`. Metrics are written per run and to
  `reports/metrics/latest.json`; models and processed tables are ignored.
- `scripts/train_text_transformer.py` trains TF-IDF and AfroXLM-R from
  independently labeled `text_labels.csv` rows with explicit train/validation
  splits. The mock messages have no independent labels, so the transformer is
  correctly skipped rather than trained on circular proxy labels.
- `models/gnn.py` contains a PyTorch GraphSAGE-style edge classifier. The notebook
  compares it using a fixed training-period graph; this is experimental and not
  the online point-in-time graph updater.
- API latency reports p50/p95/p99 for warmed in-process model scoring. It
  excludes feature computation and network time.

## Limitations and review items

- **Mock metrics are rehearsal only.** Synthetic labels and event patterns come
  from the generator's assumptions.
- Transformer fine-tuning requires human-labeled text and a real pretrained
  checkpoint download. The current mock text table cannot support a valid
  supervised text experiment.
- The GNN is a static graph comparison, not a live graph model. The scoring API
  still accepts precomputed features; the real sandbox event contract is needed
  for online state updates and train/serve parity.
- Twi warning text is deliberately blocked until a native speaker records
  reviewer, review date, and approved translation in `configs/warnings.yaml`.
  This workspace cannot truthfully claim a translation has been reviewed.
- Cost thresholds, action permissions, prevalence correction, latency targets,
  real schema mapping, and cross-provider access require sandbox/domain review.
