# MoMo Fraud: Problem, Solution, and ML Strategy

**Date:** 23 November 2026  
**Project stage:** Mock-data prototype and architecture rehearsal  
**Dataset used for current demonstration:** 100,023 synthetic transactions; 22,005 labeled fraud transactions (about 22%)

## 1. The problem we are trying to solve

Mobile-money fraud is not just a question of whether an individual payment
looks unusual. The warning signs can be distributed across a sequence of
events and several kinds of records:

- A suspicious text may arrive before a victim sends money.
- A call may occur shortly before a PIN reset or wallet debit.
- A SIM replacement may precede an unfamiliar payment.
- Several wallets may pass money onward quickly.
- A newly used merchant or agent may receive payments from many unrelated
  people.
- A large stolen amount may be divided into smaller transfers.

The engineering problem is to combine the signals that are available at a
specific decision point, estimate risk quickly enough to be useful, and choose
an intervention that reduces expected harm without creating too much friction
for honest customers.

The target is not simply “maximize accuracy.” Fraud is rare in live traffic;
missed fraud and wrongly interrupted legitimate payments have different costs.
Useful objectives include:

- Catching fraud before money moves or can be cashed out.
- High recall at an agreed false-positive budget.
- Amount-weighted loss prevented.
- Low customer friction and clear explanations.
- Predictable latency and safe behavior when a model or signal is unavailable.

## 2. The solution we are building

The intended solution is a layered, event-aware fraud decision service:

1. Ingest transactions and linked call, text, SIM, wallet, complaint, and
   identity events.
2. Maintain state in event-time order and build point-in-time features.
3. Use a fast tabular model and established risk rules for the immediate
   decision.
4. Calibrate risk scores and apply cost-aware decision policy.
5. Return an action and understandable reason codes.
6. Analyze text deeply and refresh graph intelligence separately when those
   steps cannot safely fit in the immediate decision latency budget.
7. Record outcomes, investigate errors, monitor drift, and retrain only with
   validated labels.

The intended actions are allow, warn, hold, and freeze, but the live sandbox's
permitted actions and the actual costs of each action must be confirmed before
deployment.

### Intended event path

```text
Transaction/call/text/SIM event
    -> timestamped ingest and entity linking
    -> rolling state update
    -> point-in-time feature vector
    -> rules + LightGBM + anomaly feature
    -> probability blend and validation-fitted calibration
    -> expected-loss policy
    -> allow / warn / hold / freeze + reason codes
    -> log outcome for review and monitoring
```

### Fast and deep paths

```text
Fast path (must meet the payment/USSD deadline):
  state lookup + compact features + LightGBM + calibrated decision

Deep path (asynchronous or non-blocking):
  multilingual transformer + richer graph analysis + case enrichment
```

The deep path should not hold a USSD response open. If text or graph analysis
is delayed or unavailable, the service should make the fast-path decision,
record that the optional signal was unavailable, and continue according to an
approved fallback policy.

## 3. What is implemented now

The current implementation is a mock-data research prototype:

- A generator creates tables for transactions, people, SIMs, wallets, bank
  accounts, calls, texts, and complaints.
- The final transaction file is rebalanced to exactly 100,023 rows and 22%
  fraud labels for the requested rehearsal.
- An event replay produces features from strictly earlier events. Equal-time
  events are not used to score one another.
- Features cover transaction velocity and amounts, new payees, recipient
  network aggregates, call timing, message keyword flags, claimed-credit
  ledger mismatch, SIM/PIN changes, and wallet age.
- Time-ordered train/validation/test assignment groups fraud cases together;
  cases that cross boundaries are excluded.
- Rules, logistic regression, LightGBM, and an Isolation Forest score are
  evaluated. The Isolation Forest score is an input feature for the supervised
  models.
- The two supervised model probabilities are averaged, then an isotonic
  calibration model is fitted on validation predictions.
- A validation-selected threshold and an expected-loss action policy are
  applied.
- SHAP can explain the LightGBM component.
- A separate PyTorch GraphSAGE-style experiment uses a fixed training graph.
- Transformer training utilities exist, but the synthetic messages are not
  used as independently labeled text examples.
- FastAPI scores an already-computed numeric feature vector.
- Four staged notebooks, tests, model outputs, feature outputs, decisions, and
  metric reports are present.

The prototype has **not** yet demonstrated an integrated, live, end-to-end
event-to-decision path.

## 4. ML techniques: why they are used and whether they are the best choice

| Technique | Current role | Why it is a reasonable choice | Assessment |
|---|---|---|---|
| Rules | Transparent reference score | Fast, reviewable, useful before labels and as a baseline | Keep as a benchmark and safety signal; not enough alone |
| Logistic regression | Supervised tabular baseline | Simple, quick, easier to inspect and calibrate | Keep as a baseline; useful for checking whether complexity earns its place |
| LightGBM | Main supervised tabular model | Handles nonlinear feature interactions and mixed tabular signals efficiently | Strong MVP choice for tabular data; compare to the simplest baseline on real data |
| Isolation Forest | Anomaly score included as a feature | Offers a novelty signal from legitimate training examples | Reasonable experiment, but it does not itself solve unseen-fraud detection; validate its incremental value |
| Probability averaging + isotonic calibration | Fuse the two supervised scores and map them to validation-calibrated scores | Simple and relatively easy to reproduce | A practical first fusion method, not proven optimal; compare with logistic stacking on out-of-fold predictions |
| TF-IDF + logistic regression | Text baseline utility | Cheap, explainable text benchmark | Recommended first text model once independent message labels exist |
| Multilingual transformer | Planned deep text model | Can represent code-switching, context, impersonation, and manipulation language | Potentially useful but data-hungry and slower; train only on independently labeled text and do not block USSD initially |
| Graph aggregates | Historical fan-in/out and pass-through features | Capture money movement patterns with modest operational complexity | Recommended before a GNN; easy to audit and update online |
| GraphSAGE-style GNN | Separate experimental edge classifier | Learns node representations and edge patterns | Research comparison only: current graph is a fixed training snapshot, not an online rolling graph |
| SHAP | Explanation of LightGBM component | Shows which features influence tree predictions | Useful for analysts and error analysis; exact explanations need not be on the critical path |

LightGBM is a gradient-boosted decision-tree method. It uses gradients to
optimize its boosting objective, but it is not the same model family as a
neural network trained with backpropagation. For this project's tabular
transaction features, LightGBM is a sensible starting workhorse. It is not
possible to declare it the best model without real-data comparisons and
operational validation.

### Is this the best overall approach?

It is a good **staged MVP approach**, not a proven best or final architecture:

- Start with point-in-time rules and tabular features because they are fast and
  auditable.
- Use LightGBM as the primary model candidate.
- Keep logistic regression and rules as honest comparisons.
- Treat anomaly, text, and GNN signals as additional evidence, not mandatory
  complexity.
- Promote a component only when it improves a blind evaluation and can meet the
  operational requirements.

The current fusion is a simple average followed by isotonic calibration; it is
not a trained meta-model stacker. A learned stacker could help, but should be
trained on out-of-fold predictions to avoid leakage and compared on a separate
validation set.

## 5. ML workflow and pipeline

### A. Data understanding and validation

1. Inventory source tables, schemas, keys, timestamps, labels, and missingness.
2. Confirm how numbers, wallets, Ghana Cards, calls, texts, and SIM events link.
3. Confirm whether labels describe a transaction, a case, a customer, or some
   other unit.
4. Audit duplicate IDs, timestamp zones, missing events, late-arriving events,
   and fields that are only known after the decision.
5. Preserve raw files unchanged and maintain a separate blind transaction file.

### B. Define decision moments

For each action point (for example text delivery, transaction authorization,
cash-out, SIM replacement, or agent float), write down exactly which fields are
available at that moment. A feature that arrives later must not be used for an
earlier decision.

### C. Point-in-time feature creation

1. Replay all relevant events in timestamp order.
2. Compute rolling number-, SIM-, recipient-, and agent-level histories.
3. Score equal-time transactions before adding those transactions to state.
4. Exclude labels, scenario names, fraud roles, and case IDs from `X`.
5. Reuse the same feature logic for offline replay and live serving.

### D. Splitting and training

1. Use a chronological train/validation/test split.
2. Keep every fraud case in one split.
3. Exclude cases crossing time boundaries instead of splitting them.
4. Fit transformations and anomaly models from training data only.
5. Train a rules baseline, logistic regression, and LightGBM.
6. Fit anomaly scoring on legitimate training-period data and measure whether
   it adds value.
7. Select calibration and thresholds using validation data only.
8. Keep the final blind test untouched until the approach is fixed.

### E. Evaluation

Report a useful set of operating metrics:

- PR-AUC (especially for class imbalance).
- Recall at one or more fixed false-positive budgets.
- Precision, false-positive rate, and false-positive count.
- Amount-weighted recall and amount stopped.
- Per-fraud-kind results.
- Frauds caught before money moved/cash-out, where event labels permit this.
- Honest activity interrupted by each action.
- Calibration plots and score distributions.
- End-to-end p50/p95/p99 latency.
- Leave-one-fraud-kind-out results to probe generalization to an unseen kind.

Do not tune the final threshold using test labels. If test-curve diagnostic
values are shown, label them as diagnostics rather than deployable operating
points.

### F. Decision and serving

1. Turn calibrated probability and amount at risk into expected loss.
2. Compare expected loss against approved action/friction costs.
3. Return permitted actions and evidence-based reason codes.
4. Keep deep text/GNN work off the synchronous path until measured.
5. Log model version, features, action, latency, and later outcome for review.

### G. Monitoring and improvement

- Monitor feature drift, score drift, missingness, false positives, and delayed
  fraud labels.
- Review customer-care and analyst feedback.
- Use controlled retraining and retain a reproducible experiment record.
- Run champion/challenger comparisons and roll back safely.
- Re-test train/serve feature parity after every feature change.

## 6. Current mock results and how to interpret them

The latest saved run is `20261123T051710201396Z`. It uses the 100,023-row mock
dataset, with 59,974 train rows, 19,947 validation rows, and 19,979 test rows.
There are 123 rows from cases crossing split boundaries that were excluded.

| Model | PR-AUC | ROC-AUC | Test recall | Test FPR | Amount-weighted recall |
|---|---:|---:|---:|---:|---:|
| Rules | 0.4902 | 0.7493 | 3.10% | 0.00% | 7.14% |
| Logistic regression | 0.9872 | 0.9955 | 1.57% | 0.00% | 1.05% |
| LightGBM | 0.9926 | 0.9976 | 0.00% | 0.00% | 0.00% |
| Calibrated probability blend | 0.9945 | 0.9978 | 51.23% | 0.00% | 63.29% |

The base supervised models have strong ranking metrics but very low recall at
the selected validation false-positive operating threshold in this test run.
This illustrates why PR-AUC or ROC-AUC alone is not enough. The validation
thresholds for the probability models are very close to `1.0`; calibration and
threshold behavior need careful review before an operational claim.

The ensemble caught 2,283 of the 4,456 test fraud rows and missed 2,173. It
stopped about GHS 5.62 million of synthetic fraud amount. It produced zero
false positives among 15,523 synthetic legitimate test transactions, but this
is a finite mock sample result, not a guarantee of zero real customer impact.

Per-kind ensemble recall varies widely: it is about 65.7% for mule chain and
64.3% for agent fraud, versus 16.7% for fake promo and 23.3% for relative
impersonation. That points to likely value from text and sequence features, but
the mock results do not prove a transformer will solve those misses.

The test set contains roughly 22% fraud, unlike a realistic production payment
stream. Do not extrapolate its precision, action rates, or cost results directly
to the live population. Prevalence adjustment and real operational costs are
needed for production decision thresholds.

The latency report measures only warmed in-process model scoring over 200
samples: p50 `31.28 ms`, p95 `51.30 ms`, and p99 `130.21 ms`. It excludes feature
construction, state/database access, HTTP serialization, network, and sandbox
bridge time. It therefore does not demonstrate a three-second end-to-end USSD
SLA.

## 7. How the components fit together

### Offline development

```text
Raw/mock CSVs
   -> schema mapping and validation
   -> chronological point-in-time replay
   -> numeric feature table
   -> case-aware chronological splits
   -> rules + logistic + LightGBM + anomaly score
   -> validation probability blending/calibration
   -> validation threshold selection
   -> untouched test metrics and per-kind review
   -> saved model, metric report, decisions, and SHAP analysis
```

### Intended online system

```text
Sandbox event
   -> validate and link entities
   -> update rolling state with event-time ordering
   -> compute the same feature vector as offline replay
   -> fast model and policy
   -> response with action/reasons
   -> asynchronous deep text/graph enrichment
   -> outcome logging and monitoring
```

At present, the offline workflow is substantially implemented. The online
workflow stops at a scoring endpoint that accepts already-computed features;
the actual event adapter and rolling live state are not complete.

## 8. Gaps, implementation requirements, and recommendations

### Real sandbox data and labels

**Gap:** The current evaluation uses generated data. Team credentials are not
available here, and no real sandbox data has been verified.

**Needed:** Connect with the team's credentials, download raw answer and blind
tables, validate actual schemas and timestamp semantics, then rerun the leakage
audit before training.

### Transformer text model

**Gap:** Training code exists, but the mock text has no independent text labels.

**Needed:** Create a reviewed `text_labels.csv` with `text`, `is_fraud`,
`split`, and ideally `fraud_case`. Labels must come from independently reviewed
messages/investigations, not from the generator's scenario labels. Start with
TF-IDF + logistic regression; promote a multilingual transformer only if it
improves case/time-separated evaluation and can be served within the chosen
architecture.

### GNN

**Gap:** The GNN is static. Its graph is formed from training transactions once;
later validation/test edges are scored against that unchanged snapshot.

**Needed:** Build rolling graph state from prior events only, add edges
incrementally, prove offline/live graph parity, and benchmark graph updates.
First exhaust simpler fan-in, fan-out, pass-through, and rapid-hop features.
Use a GNN only if it adds reliable blind-test performance beyond those
aggregates.

### Twi warnings

**Gap:** Twi output is blocked because no native-speaker review has been
recorded.

**Needed:** Have a native Twi speaker and customer-care reviewer approve
translation, dialect/register, meaning, and date. Record the approval in
`configs/warnings.yaml`; keep the API block until then.

### Live event state and API integration

**Gap:** `/score` accepts precomputed features. It does not yet consume real
transaction, call, text, SIM, or USSD events and update rolling state.

**Needed:** Implement event schemas, event-time state updates, identity linking,
late-event handling, state expiry, and replay-vs-live feature equality tests.
Use the real starter-kit plugin contract once available.

### USSD SLA and reliability

**Gap:** Current latency excludes most of the request path.

**Needed:** Benchmark event ingest, state lookup, feature construction, model,
calibration, action policy, serialization, bridge, and network under realistic
concurrency. Set a hard response deadline below the stated session limit and
leave margin for network variability. Ensure the fast path can decide without
the transformer or GNN; record optional-signal timeouts rather than blocking.

### Calibration and decisions

**Gap:** Placeholder costs/actions and synthetic prevalence make current action
rates unsuitable for deployment.

**Needed:** Agree intervention costs, allowed actions, expected fraud loss,
legitimate-customer friction, and acceptable FPR with the sandbox/business team.
Tune thresholds on validation data using a realistic prevalence estimate. Keep
blind test results separate from the threshold-selection loop.

### Generalization and model evidence

**Gap:** A 22% synthetic fraud prevalence and scenario-generation artifacts can
make model results optimistic or distort feature learning.

**Needed:** Validate on real data; test a held-out time period; run
leave-one-fraud-kind-out experiments; audit SHAP for amount/timing artifacts;
report error examples and customer friction; assess calibration and drift.

## 9. Recommended order of work

1. **Get real sandbox access and confirm dataset semantics.**
2. **Profile and map the actual tables; audit label quality and timestamp
   availability.**
3. **Run leakage checks and define decision points for each permitted action.**
4. **Build the fast, point-in-time tabular baseline and prove offline/live
   parity.**
5. **Use case-aware chronological splits and a genuinely untouched blind set.**
6. **Agree costs and actions, calibrate on validation, and report recall at
   fixed FPR plus customer friction and amount-weighted outcomes.**
7. **Measure complete request latency with the real bridge and realistic
   concurrency.**
8. **Collect independent text labels and native-reviewed Twi wording.**
9. **Add text-model and rolling-GNN components only if they improve the blind
   evaluation without breaking latency, reliability, or explainability.**
10. **Add monitoring, delayed-outcome capture, analyst feedback, retraining
    controls, and rollback.**

## 10. Bottom line

The current approach is a sensible, explainable starting point for the hackathon:
time-aware features, case-aware evaluation, a strong tabular candidate, a
cost-aware decision layer, and optional deep signals. It is not yet possible to
claim that this is the best model or a working production detector.

The next major improvement is not simply “use a bigger neural network.” It is
to obtain real labeled data, establish trustworthy decision-time features,
prove offline/live parity, use realistic costs and prevalence, and measure the
whole service under its real latency budget. Deep text and graph models should
be added only where they demonstrably improve that evidence.

## References within this workspace

- Current implementation/status: `reports/project_status_and_next_steps.md`
- Current run metrics: `reports/metrics/latest.json`
- Feature replay: `src/momo_fraud/features/state.py`
- Experiment orchestration: `src/momo_fraud/pipeline.py`
- Decision policy: `src/momo_fraud/decision.py`
- Scoring API: `serving/plugin_api.py`
- Ordered notebook workflow: `notebooks/01_eda.ipynb` through
  `notebooks/04_error_analysis.ipynb`
