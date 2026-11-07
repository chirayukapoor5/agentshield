# Research results summary — November 7, 2026

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
- **One live Groq tool-use canary is now independently logged.** On November 7,
  model `openai/gpt-oss-120b` completed 2 real chat requests and generated
  1 `read_note` tool call, which was allowed. No email call was attempted by
  that real model, and no email handler executed. See
  [verified run #42369186158](https://github.com/chirayukapoor5/agentshield/actions/runs/42369186158)
  and `docs/LIVE_MODEL_CANARY_2026-11-07.md`. **Not an attack-success-rate result.**
- Optional real LangChain/LangGraph `ToolNode` adapter, tested against the
  actual framework with synthetic messages and zero model requests; unlike
  a browser simulation, this exercises live Python framework execution.
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
not complete. The verified single Groq tool-use canary does **not** establish that the
SDK blocked a malicious tool request from a real model: the real model only
requested the allowed `read_note` tool. The same workflow's scripted attack
request is a synthetic unit canary, not model-generated evidence.

**Do not fill the missing counts or denominator with invented values.**
Historical AgentShield website-scanner QA is unrelated to these hypotheses.

See `docs/RESEARCH_EXECUTION_RUNBOOK.md` for reproducibility gates and
`docs/IMPLEMENTATION_STATUS_2026-11-06.md` for the detailed implementation table.
