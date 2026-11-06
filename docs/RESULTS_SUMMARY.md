# Research results summary — November 6, 2026

**No completed official AgentDojo C1–C4 experiment matrix is available.**
No measured multilingual attack-success rate (ASR), matched C3/C4 effect,
per-language classifier robustness, or cross-defense utility result can be
reported. Do not use SDK unit tests or synthetic tool demonstrations as
security efficacy estimates.

## What can be independently inspected

- Local AgentShield SDK tool-call authorization tests, now covering a bounded
  multi-turn model loop, redacted execution metadata and policy snapshots.
- Previous Groq connectivity preflight: 20/20 successful chat-completion calls
  (not a tool-calling or injection benchmark).
- Offline AgentDojo installation/suite/pipeline construction checks in CI,
  without victim-model inference.
- C1 and C2 adapters for the official task checkers, with normalized JSONL
  metadata, redacted trace files, and strict translated-input gates.
- A C3/C4 development/tune-only adaptive pilot using a budgeted attacker-model
  proposer and official security checker as a training oracle.
- Paired comparison, trace-audit and uncertainty-analysis code, exercised
  with synthetic unit-test fixtures **only**.

## Explicit missing evidence

The reviewed multilingual attack corpus, learned-classifier configuration,
independently audited held-out C1–C4 traces, and repeated model/seed runs are
not complete. Real Groq local-tool execution may be run via the manual workflow,
but must be separately verified from a specific GitHub Actions artifact before
citing results.

**Do not fill the missing counts or denominator with invented values.**
Historical AgentShield website-scanner QA is unrelated to these hypotheses.

See `docs/RESEARCH_EXECUTION_RUNBOOK.md` for reproducibility gates and
`docs/IMPLEMENTATION_STATUS_2026-11-06.md` for the detailed implementation table.
