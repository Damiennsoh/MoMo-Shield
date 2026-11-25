================================================================================
MoMo Shield — ABLATION TABLE TEMPLATE (fill with Fraud Console numbers only)
================================================================================
RULE: every cell must come from an observed InnoFemme Fraud Simulator /
Fraud Console run at the same "honest wrongly stopped" operating point.
Local fixture runs do NOT count. Leave cells blank rather than estimate.

--------------------------------------------------------------------------------
CONFIGURATIONS (run the same scenario set through each)
--------------------------------------------------------------------------------
A. Allow-all baseline      — plug-in always returns {"decision":"allow"}
B. Rules only              — deterministic rules + payload signals;
                             Glance/SIM-swap/NIA/ledger disabled
C. Rules + external intel  — adds Glance, SIM-swap, NIA, threat ledger
D. Rules + RAG/KG          — adds lexical + semantic case-corpus matching
E. Full stack (current)    — C + D + OTP defense + blast + velocity
F. Rules + ML (Phase 2)    — feature-flagged LightGBM blended score,
                             ONLY if it beats E on the console

--------------------------------------------------------------------------------
MEASUREMENT GRID (per configuration, per fraud typology)
--------------------------------------------------------------------------------
Fraud typologies to cover (from the case corpus / simulator kinds):
  GH01 reversal scam · GH02 fake credit · GH15 phishing link ·
  credential harvest · OTP read-out · money mule · SIM-swap takeover ·
  nuisance preconditioning · RTP abuse · structuring · blast SMS

For EACH typology × configuration record:
  - incidents injected (n)
  - stopped at plug-in (reject/delay) ....... count + %
  - warned (warn decision) .................. count + %
  - got through (allow) ..................... count + %
  - honest wrongly stopped .................. count + %  ← THE key metric
  - median decision latency (handler ms) .... observed value

--------------------------------------------------------------------------------
ROLLUP TABLE (what goes on the slide)
--------------------------------------------------------------------------------
| Configuration        | Fraud stopped | Warned | Got through | False pos. | p50 ms |
|----------------------|---------------|--------|-------------|------------|--------|
| A. Allow-all         |      —        |   —    |     —       |     —      |   —    |
| B. Rules only        |              |        |             |            |        |
| C. + External intel  |              |        |             |            |        |
| D. + RAG/KG          |              |        |             |            |        |
| E. Full stack        |              |        |             |            |        |
| F. + ML (if ready)   |              |        |             |            |        |

--------------------------------------------------------------------------------
WHAT THE SLIDE SHOULD SAY
--------------------------------------------------------------------------------
Title idea: "Every layer earns its place — measured, not claimed."

Narrative beats:
1. Allow-all → 0% stopped (the problem is real)
2. Rules-only → bulk of typologies caught; shows deterministic core works
3. +Intel → catch rate on cross-operator/known-bad scenarios improves
4. Full stack → best recall AT the same false-positive operating point
5. (If ML ships) → marginal gain over E justifies Phase-2 investment;
   if not, say so honestly: "ML is staged behind a flag pending retrain
   on the full 100k dataset" — that IS the responsible-engineering pitch.

Key honesty line for judges:
"We tuned for the metric the brief actually punishes: honest activity
wrongly stopped. Every configuration above was compared at the same
false-positive budget."

--------------------------------------------------------------------------------
HOW TO RUN (practical)
--------------------------------------------------------------------------------
• Feature-flag toggles needed (add to .env / config.py):
    INTEL_LOOKUPS_ENABLED=true|false   (Glance/SIM-swap/NIA/ledger)
    RAG_ENABLED=true|false             (lexical + semantic KB scoring)
    ML_SCORER_ENABLED=false            (Phase 2 slot — already reserved)
• For "rules only": set INTEL_LOOKUPS_ENABLED=false RAG_ENABLED=false
• Record Fraud Console scorecard per run; screenshot/CSV each
• Same incident set (kinds + counts) across all configurations
================================================================================
