# AgentShield 10,000-case security-contract stress report
**Verified:** 2026-11-07. **Suite:** `guard-stress-v2`, seed `20261107`.

## Reproducible CI evidence

- [Successful 10k CI run #42371225324](https://github.com/chirayukapoor5/agentshield/actions/runs/42371225324)
- [Python 3.10 report artifact](https://github.com/chirayukapoor5/agentshield/actions/runs/42371225324/artifacts/13573449496)
- [Python 3.12 report artifact](https://github.com/chirayukapoor5/agentshield/actions/runs/42371225324/artifacts/13573518836)
- The same source and seeded cases ran on both Python versions.
- Each environment ran **10,000/10,000 passing deterministic contract cases**,
  with **0 observed failures** and **0 real model or external network calls**.
  Across both environments: **20,000 case executions**.
- The case-sequence SHA-256 for both environments:
  `ab0d0dae3e781ab848e41730ad9143b05f5dcd6d661973ad1f86f489e786f639`.
- Harness self-tests include an *intentional fail-open policy mutation* to
  verify that the test oracle catches unauthorized tool execution.

## Cases and observed effects (per Python version)

| Family | Executed | Passed | In-memory handler calls | Invariant |
| --- | ---: | ---: | ---: | --- |
| Unlisted/obfuscated tool names | 2,500 | 2,500 | **0** | Exact tool-name allowlist prevents near-match names from executing |
| URL destination allowlist | 2,500 | 2,500 | **500** | Only constructed exact-host HTTPS requests pass; 2,000 invalid or adversarial destination forms are blocked |
| Approval and audit fail-closed rules | 2,000 | 2,000 | **750** | Only genuine approvals execute; audit failures, truthy non-booleans and callback exceptions deny; approved arguments are immutable snapshots; replay needs fresh approval |
| Malformed model tool-call batches | 2,000 | 2,000 | **0** | Bad JSON, duplicates, NaN/Infinity, oversized payloads, unexpected envelopes and isolated Unicode surrogates reject the whole batch before the valid preceding handler |
| Valid multilingual/code-mixed inputs | 1,000 | 1,000 | **1,000** | Authorized read-only tool preserves the original international input exactly; attacker-like text is treated as data |
| **Total** | **10,000** | **10,000** | **2,250** | All local contract assertions passed |

**Definitions:** `passed` means the expected allow/deny result and handler
side-effect count matched that test's constructed ground truth.
`handler calls` are process-memory fixture functions, not actual email,
file deletion, shell or network egress.

These generated tests deliberately include repeated classes with different
case indices, text, URLs and approval inputs. They are **not** 10,000
independent observed prompt-injection attacks, so the 100% contract pass
fraction must not be called an attack-detection score or assigned a Wilson
CI meant for independent random trials.

## Hardening found and implemented

The OpenAI-compatible `dispatch_chat_tool_calls` argument validator could
previously raise an unnormalized `UnicodeEncodeError` when a model returned
unpaired surrogate characters inside raw JSON. Python's `json.loads` also
accepts escaped isolated surrogates in tool argument keys/values. The
dispatcher now:

1. Rejects oversized raw strings **before** allocating UTF-8 copies.
2. Converts failed UTF-8 encoding to `MalformedToolCalls` for the entire
   batch.
3. Iteratively rejects unpaired surrogates after JSON decoding, including
   nested arguments, names and tool-call IDs.
4. Validates all calls before invoking the first handler.

Six additional explicit SDK regression cases target this class of malformed
data; both Python SDK CI configurations passed.

## How to reproduce

```bash
git checkout research/multilingual-injection-2026
python -m pip install -e ./sdk
PYTHONPATH=sdk:. python scripts/run_guard_stress.py \
  --cases 10000 --seed 20261107 \
  --output data/runs/guard-stress/summary.json
PYTHONPATH=sdk:. python -m pytest -q tests/test_guard_stress.py
```

The report contains counts, failures (up to the first 25 **redacted** case
IDs), a deterministic case-sequence hash, wall-clock duration and explicit
`is_prompt_injection_ASR=false` metadata. A nonzero failure exits with a
nonzero status so the GitHub release gate fails.

The harness accepts a bounded `--cases` value up to **100,000** for a
larger optional offline run; the verified result above is **10,000 cases per
Python version**, not 100,000.

## Remaining limitations and next higher-value tests

The policy SDK guards *registered* Python tool handlers; raw direct function
calls bypass it. Host allowlisting does **not** protect against DNS rebinding,
server redirects or subsequent network calls made inside a permitted handler.
Human approval callback identity, expiration, storage, concurrency and
account-level consent must be provided by the host application. Authorized
handlers still need operating-system/network sandboxing when untrusted.

The 10k suite cannot evaluate the model's response to prompt injection.
For actual defense efficacy, run a properly blinded and scored AgentDojo
C1–C4 experiment with frozen language-reviewed attack payloads, a fixed
attacker-query budget, both attack-success and legitimate-task-utility
checkers, trace provenance, per-language denominators, and uncertainty
analysis. Those empirical metrics are **not available yet**.
