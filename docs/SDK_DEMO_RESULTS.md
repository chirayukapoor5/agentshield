# AgentShield Guard SDK — verified local demo results

**Date:** 2026-11-05  
**Scope:** local, deterministic Python tool-wrapper policy test; synthetic examples only.  
**Source:** [SDK tests](../sdk/tests/test_guard.py), [demo](../sdk/examples/demo_stats.py), [implementation](../sdk/agentshield_guard/guard.py).

## Reproduction
From repository root, after installing `pytest`:

```bash
python -m pip install ./sdk
python -m pytest -q sdk/tests
python sdk/examples/demo_stats.py
```

## What was actually observed
During a local execution of the SDK code in the engineering environment:
- Unit tests: **11 passed**, 0 failed.
- Deterministic policy scenarios: **8 / 8** expected decisions matched.
- Decision breakdown: **2 allowed**, **6 denied**.
- Calls to real LLM providers: **0**.
- AgentDojo benchmark trials in this demo: **0**.

All policy scenarios are synthetic. They use an explicit allowlist and approval-required tool names; no unauthorized account, domain, credential, or live network was tested.

| Scenario | Expected | Observed |
| --- | --- | --- |
| Allowlisted document read | allow | allow |
| Email send without approval callback | deny | deny |
| File delete without approval callback | deny | deny |
| Shell tool not registered | deny | deny |
| HTTPS fetch to allowlisted hostname | allow | allow |
| HTTPS fetch to unlisted hostname | deny | deny |
| Plain HTTP fetch | deny | deny |
| Lookalike/extended hostname | deny | deny |

## Claims these results do *not* support
The 8/8 toy decisions are **not** prompt-injection attack success rate, real-world security efficacy, classifier accuracy, multilingual robustness, or evidence that existing agents are protected automatically. A malicious model can still choose unsafe arguments inside an allowed tool; this SDK does not inspect content or apply a model classifier. A developer must register the SDK wrappers for each tool; direct calls bypass enforcement. URL hostname checks do not guarantee DNS pinning or prevent a transport from following unsafe redirects.

## Next release gates
1. Validate SDK in continuous integration across Python versions.
2. Implement a tested framework adapter and signed policy distribution; add negative security tests for bypass and argument injection.
3. Run controlled AgentDojo official utility/security checkers with model versions and token budgets logged.
4. Report paired ASR, utility, failures, confidence intervals, and language-validation status before making any empirical defense-effectiveness claim.
