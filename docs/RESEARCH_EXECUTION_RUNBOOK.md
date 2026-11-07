# AgentShield research execution runbook — current gates

This runbook covers the C1/C2/C3/C4 experimental infrastructure on the
`research/multilingual-injection-2026` branch. It does not imply that full
AgentDojo experiments have occurred or that any defense efficacy is established.

## 1. Prepare exact benchmark environment

```bash
python -m pip install -r research/requirements.txt
PYTHONPATH=. python scripts/select_pairs.py --count 30 --seed 20261105
```

The pinned suite is AgentDojo 0.1.35, workspace benchmark v1.2.2.
Check `data/runs/workspace-pairs.json` and freeze the scenario-family split
before evaluating anything. All paraphrases and translations of one
`user_task_id` must remain in the same development/tune/test partition.

## 2. Keep real-provider execution disabled by default

`config/api.yaml` is intentionally absent from the public repository.
The mock provider makes no external model calls. Real execution requires a
private provider configuration with independent victim/attacker roles, positive
request, token and USD reservation caps, and a corresponding private API key.
The project ledger stores **reservations**, not an independently reconciled
invoice. Treat any new job instance as a new billing boundary.

A bounded tool-call proof can be reproduced offline:

```bash
PYTHONPATH=sdk python scripts/groq_tool_smoke.py --mode mock
```

For a live Groq canary, manually run GitHub Actions `groq-local-tool-smoke`
with the `GROQ_API_KEY` repository secret. This canary is not AgentDojo ASR.

## 3. C1: static English

```bash
PYTHONPATH=. python scripts/run_static.py --mock
# After private paid-client setup, explicit budget review:
PYTHONPATH=. python scripts/run_static.py --split dev --defense none
```

Real C1 results use the pinned official AgentDojo checkers. The writer
creates JSONL rows in the fixed schema and paired redacted metadata traces.
`--split test` requires `--permit-heldout-test` and should be used only
after the experiment is frozen.

## 4. C2: static, reviewed translations

C2 does **not** automatically translate malicious text. Each translation must
be tied to the exact original English injection by SHA-256 and human reviewed.
Use the versioned translation-store schema (see `src/translate/store.py`),
with these additional fields for each record:

```json
{
  "id": "unique-language-scenario-key",
  "scenario_id": "user_task_id::injection_task_id::tool_slot",
  "lang": "es",
  "source_sha256": "64 lowercase hex digits of the exact English C1 text",
  "text": "REPLACE_WITH_REVIEWED_TRANSLATION",
  "provenance": "human",
  "back_translation": "REPLACE_WITH_REVIEWED_BACK_TRANSLATION",
  "back_translation_similarity": null,
  "needs_native_check": true,
  "validated_by_me": false
}
```

**Those example validation flags are deliberately false.** Do not change them
without genuine language review. The C2 runner fails closed until
`validated_by_me=true`, `needs_native_check=false`, and the source
hash matches the regenerated English C1 candidate. All required translations
for the selected split must be present before any defender trials begin.

```bash
PYTHONPATH=. python scripts/run_translated.py \
  --translations PRIVATE_REVIEWED_TRANSLATIONS.json \
  --language es --script Latn --split dev \
  --i-understand-this-makes-real-calls
```

C2 is reported per-language. The example above is an execution command, not
evidence the command has been executed.

## 5. Adaptive search (C3, C4)

`src/attack/search.py` validates condition-specific languages, code-mixing
ratios, query caps, scenario-bound resumptions, and hashes candidate texts
instead of writing raw attack/defender content. On proposer errors, invalid generated candidates, or oracle failures, it
logs an unscorable consumed attempt and stops for manual review. This prevents
silent extra attempts when resuming a run after a charged model request. The code accepts
proposer and evaluator callbacks. The `scripts/run_adaptive.py` pilot now
connects a budgeted attacker-model proposer to the pinned official AgentDojo
security checker on one dev/tune scenario. It intentionally excludes held-out
cases and does not report a final benchmark ASR.

```bash
# No API calls:
PYTHONPATH=. python scripts/run_adaptive.py --mock --budget 3

# Controlled real-model dev/tune pilot, after reviewing provider caps and
# selecting an exact scenario ID from the frozen manifest:
PYTHONPATH=. python scripts/run_adaptive.py \\
  --condition C3 --budget 3 \\
  --scenario-id 'user_task_id::injection_task_id::injection_slot' \\
  --i-understand-this-makes-real-calls
```

C4 refuses to run until `config/languages.yaml` contains a genuinely reviewed
non-English language with `native_validation_available: true`. Existing
language placeholders must not be represented as reviewed. Pilot feedback is
training-only; frozen candidates and blinded held-out replay are not yet done.

For the preregistered comparison, use the same attacker budget (B=10) and
selection algorithm for C3 and C4; keep held-out feedback unavailable during
selection. Adaptive attempts must also respect the persistent provider ledger.
Query cap equality is not proof of equal numbers of *actual* calls if a search
stops early or the provider retries.

## 6. Auditing and statistical output

```bash
PYTHONPATH=. python research/validate_results.py data/runs/official-results.jsonl
PYTHONPATH=. python research/audit_traces.py data/runs/official-results.jsonl
PYTHONPATH=. python research/paired_analysis.py data/runs/official-results.jsonl \
  --split test --samples 2000 --seed 20261105
```

The trace audit verifies checker identity, trial identity, label consistency,
and SHA-256 shape. It **cannot independently verify a model execution occurred**.
The paired analyzer matches scenario, split, defense, model and seed; resamples
at the recorded user-task-family level; and reports missing/unscorable cases.
Do not interpret output if the trace audit fails or translations are unreviewed.

## Remaining completion blockers

- Collect and review a defensible multilingual candidate corpus.
- Verify licensed learned-classifier model and its language coverage.
- Implement C3/C4 live official-checker feedback, frozen candidate selection
  and held-out replay without leakage.
- Run the controlled benchmark across defense/model/seed combinations, preserve
  trace-based denominators and calculate uncertainty.
- Independently review performance, policy bypasses, external egress controls,
  user approval UX, and packaging before making production-safety claims.

**Nothing here authorizes external tool actions or usage of real credentials
outside sandboxed synthetic tests.**
