# Do multilingual adaptive attacks erode prompt-injection defenses? (Report draft)
**Status:** 2026-11-05; study not yet executed. All result values intentionally blank.

## 1. Abstract
Research question, controlled suite, compared defenses, paired C3/C4 comparison. **Results: not run.**

## 2. Introduction and related work
AgentDojo supports realistic simulated tool-use evaluations. Multilingual and adaptive work already exists (see RELATED_WORK); this study is a small replication/interaction test, not a novelty claim.

## 3. Methods
One suite; seeded ~30 pairs; four conditions, benign utility control; identical adaptive budgets; disjoint scenario-family splits. AgentDojo official security and utility checkers only. Classifier coverage and translation validation noted per language. Record prompt/tool formatting, model revision and provider budgets.

## 4. Results
Table: C1/C2/C3/C4 per defense and language; n, ASR and 95% CI. Plot: ASR-vs-query-budget (paired denominators). Utility, detection misses, refusal rate, timeouts and requests per success. **Not evaluated.**

## 5. Discussion
Examine H1/H2/H3 with paired uncertainty and selection-bias caveats. Distinguish machine-translation effects from language effects.

## 6. Threats to validity and reproducibility
See LIMITATIONS, pinned manifest, config and result traces. Failures and negative results are publishable.
