# AgentShield implementation status — 2026-11-06

This document separates verified engineering checks from experimental evidence.
The GitHub research pull request remains a work-in-progress; this is **not**
a claim that the research protocol or a production agent-security product is complete.

## Implemented

| Area | Status | What is actually covered |
| --- | --- | --- |
| Python tool guard | Implemented, unit tested | Exact tool allowlists, approval-required actions, destination hostname checks, audit fail-closed, execution-argument JSON snapshots |
| Local chat tool dispatcher | Implemented, unit tested | Standard chat-completions function calls, strict argument JSON, duplicate-key refusal, unknown-tool refusal, batch/byte limits, redacted errors |
| Bounded model loop | Implemented, unit tested | Multiple model turns, local function calls through AgentShield, model/tool-call budgets, sanitized decision metadata |
| Groq transport | Implemented, unit tested with fake HTTP | Fixed HTTPS provider endpoint, bounded response, timeout, sanitized HTTP/transport errors, private credential |
| Groq connectivity preflight | Real provider, verified previously | 20/20 HTTP 200 chat-completion requests. This was NOT a tool-call ASR test |
| Tool-call canary | Scripted mock passed in CI | Controlled note content and simulated email, no outbound-email capability, no real-model ASR |
| Real Groq tool-call smoke | Manual workflow available | At most three model requests, provider credential secret, redacted report; do not call verified until a run and artifact are inspected |
| AgentDojo static result schema | Implemented, offline-tested | C1 official checker output mapped to research JSONL validator; paired redacted metadata traces; held-out split must be explicitly unlocked |
| AgentDojo multilingual comparison | Not completed | C2 validated translations, C3/C4 officially scored adaptive attacks, language coverage, classifier threshold and held-out reporting remain |
| Demo dashboard | Static/synthetic | Policy playback and links to CI; not real-time production telemetry |
| Production policy enforcement | Not completed | DNS/redirect safety, direct unwrapped calls, sandbox/egress isolation, approval UX, signed distributed policies |

## Reproduction

Local SDK and mocked model-loop regression tests:

```bash
python -m pip install -e ./sdk 'pytest>=8,<10'
python -m pytest -q sdk/tests
PYTHONPATH=sdk python scripts/groq_tool_smoke.py --mode mock
```

Offline research tests:

```bash
python -m pip install 'pytest>=8,<10' 'PyYAML>=6.0.1,<7'
python -m pytest -q tests research/test_validate_results.py
```

Manual, bounded live smoke, with the existing `GROQ_API_KEY` secret:

```bash
PYTHONPATH=sdk python scripts/groq_tool_smoke.py --mode live \\
  --i-understand-this-makes-real-calls
```

Alternatively run `.github/workflows/groq-tool-smoke.yml` via GitHub
Actions → `groq-local-tool-smoke` → Run workflow. Inspect the JSON artifact.
Provider errors or unscorable episodes must **not** be counted as successful
security defenses. All example actions and email addresses are synthetic.

## Research completion gates

1. Verify and freeze exact AgentDojo version, workspace pair families and disjoint dev/tune/test partitions.
2. Validate C2 translations with provenance and human checks; report each language, not a pooled headline.
3. Integrate and pin a licensed learned classifier with known non-English coverage, matching H1.
4. Implement officially scored C3/C4 feedback with identical attacker query budgets and separate held-out evaluation.
5. Produce trace-backed eligible denominators, utility measures, unknown/unscorable counts, paired cluster bootstrap intervals and reproducible run manifests.
6. Perform external independent review before deployment or any production security guarantee.

## Attribution discipline

Do not describe the scripted offline mock as a successful prompt-injection
attack on a real model. Do not call SDK tests attack success rate.
The project is a research prototype and SDK experiment, not certified software.
