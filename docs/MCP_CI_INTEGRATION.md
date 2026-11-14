# AgentShield CI intelligence over MCP

This separate Python integration exposes four read-only tools through the official
MCP Python SDK v2.3.0. It uses the existing `AgentShield.guard` boundary and defaults
to local stdio. It is a portfolio prototype, not a production remote service or a
claim of prompt-injection prevention efficacy.

`backend/app/mcp_server.py` is an unrelated database-writing policy evaluator.
This integration neither imports nor modifies that module.

The SDK and MCP integration are also available on `main` following promotion
from the research branch. The MCP reader intentionally retains its fixed research
branch scope. The research harness and its report-upload workflow remain on that
branch; the SDK and MCP report-upload workflows also run on `main`.

## Installation and use

From the repository root, use Python 3.12. The core SDK remains Python >=3.10;
MCP's separate package requires >=3.11 and CI uses 3.12.

```bash
python3.12 -m venv .venv-mcp
source .venv-mcp/bin/activate
python -m pip install ./sdk './integrations/mcp_ci[test]'
python -m agentshield_mcp_ci
```

On Windows, create the environment with `py -3.12 -m venv .venv-mcp` and activate
with `.venv-mcp\Scripts\Activate.ps1`. Configure an MCP host to launch that
environment's Python executable with arguments `-m agentshield_mcp_ci`.
The process speaks MCP on stdin/stdout; it does not start an HTTP listener.

Public run metadata needs no token. An optional `GITHUB_TOKEN` must be limited to
this repository with **Actions: read**. The server cannot enforce the permissions
of a supplied credential; it enforces fixed-origin GET-only requests itself.
Tokens are never part of tool arguments, returned payloads or audit records.

## Tools and schemas

| Tool | Inputs | Result |
| --- | --- | --- |
| `list_ci_runs` | `workflow`: null or `sdk`, `research`, `guard-stress`, `mcp-ci`; `limit`: integer 1–20, default 10 | bounded sanitized run metadata |
| `get_ci_run` | `run_id`: positive integer | run metadata, at most 20 jobs, failed step numbers, truncation flag |
| `get_test_summary` | `run_id`: positive integer; `python_version`: null, `3.10`, `3.12` | sanitized local report totals or `report_unavailable` |
| `list_failed_tests` | `run_id`: positive integer; `limit`: integer 1–20, default 10 | opaque SHA-256 test identifiers or `report_unavailable` |

Booleans and numeric strings are not integers at this boundary. Extra tool
arguments are rejected. There are no repository, branch, URL, path or shell
arguments. All tools include `source`, UTC `retrieved_at`, `is_fixture` and a
status. Expected failures are explicit statuses; network errors never become
successful empty results. MCP itself rejects unknown tools and invalid arguments.
Use MCP `tools/list` for the exact generated JSON input/output schemas.

Scope is fixed to `chirayukapoor5/agentshield` and
`research/multilingual-injection-2026`. Allowed workflow files are `sdk.yml`,
`research.yml`, `guard-stress-10k.yml`, `mcp-ci.yml`. By-ID lookups verify the same
scope before requesting jobs. This intentionally excludes feature-branch runs.
Lists inspect one bounded page; an unfiltered page can include fewer allowed
workflows than requested. Filter by workflow for its recent history. There is no
claim of exhaustive history or aggregation over all runs.

## Test-report pipeline

The SDK, research offline and MCP workflows produce local JUnit XML, convert it,
and upload **only sanitized JSON** using `if: always()`. Artifact names are
`ci-summary-sdk-py-3.10`, `ci-summary-sdk-py-3.12`,
`ci-summary-research-py-3.12`, and `ci-summary-mcp-ci-py-3.12`.
SDK matrix versions retain distinct artifacts. XML is not uploaded.

```bash
python -m pytest -q integrations/mcp_ci/tests --junitxml=.ci-reports/mcp.xml
python scripts/export_ci_test_summary.py --input .ci-reports/mcp.xml \
  --output .ci-reports/run-123-py-3.12.json --run-id 123 --python-version 3.12 --fixture
```

Use `--fixture` for synthetic/local demonstrations. CI passes its real
`github.run_id` and does not pass that flag. Exported JSON contains schema version,
run ID, Python version, passed/failed/skipped/error/total counts, duration, opaque
identifiers of failures/errors, and the fixture marker. Identifiers hash the JUnit
classname and test name, including any parametrization: they are pseudonymous,
not proof of anonymization, and known test IDs can be correlated by hashing them.
No raw names, captured output, stack traces, assertion messages or properties are
copied. UTF-8 XML only; DTD/entity declarations and malformed structures are
rejected. Bounds: 10 MiB XML, 3,000 test cases, seven days aggregate duration,
256 KiB JSON. The exporter uses only the Python standard library.

Remote artifact ZIP download and extraction are deliberately unsupported. There
is no redirect or archive extraction surface. Missing or expired remote artifacts
are never replaced with fixtures. To serve a genuine report, an operator must
verify its origin and run association, place the sanitized JSON in a trusted
directory as `run-RUN_ID-py-VERSION.json`, and set `AGENTSHIELD_REPORT_DIR` before
launching. This local filename/schema association is not cryptographic provenance.
Do not populate it from untrusted contributors without verification. No remote
artifact result is claimed by the local report reader.

When version is omitted, local lookup prefers 3.12 then falls back to 3.10;
`list_failed_tests` uses the same rule. It does not merge matrix results.

## Demonstrations and verification

```bash
python -m pytest -q integrations/mcp_ci/tests
python integrations/mcp_ci/examples/ci_triage_demo.py --offline
python integrations/mcp_ci/examples/ci_triage_demo.py --live
```

Offline mode makes real MCP client calls against explicitly labelled fixtures.
Live mode retrieves real public GitHub metadata and reports unavailable granular
results honestly. Live networking is outside the default tests, whose socket
connections are blocked. The optional model mode is manual-only and uses bounded
Groq transport plus the existing AgentShield model-tool loop; run `--help` for
its explicit opt-in flags. It uses fixtures only, and its mocked transport tests
are not evidence of a successful real-model call.

For core compatibility, install `./sdk[langgraph,test]` and
`scikit-learn>=1.5,<2` in separate Python 3.10 and 3.12 environments, then run
`python -m pytest -q sdk/tests`. MCP must not be installed in the 3.10 environment.
The sklearn dependency is needed by the existing anomaly tests; the first clean
baseline run without it had one failure. SDK CI now installs it explicitly.

## Threat model and limits

- MCP tool inputs, GitHub API payloads and local report content are untrusted.
  Only application-owned guarded handlers are registered. An empty custom
  `ToolPolicy` denies all tools. An audit callback failure denies before I/O.
- Requests use a fixed HTTPS origin, GET only, no redirects, no environment
  proxy inheritance, short connect/read timeouts, a bounded stream and response
  size. No API writes, re-runs, logs, arbitrary URLs or downloaded archives exist.
- Upstream job/step names and arbitrary URLs are omitted. Failed step **numbers**
  are returned because upstream names can contain sensitive text. GitHub links
  are constructed from verified IDs and the fixed repository.
- JSON validation rejects unknown fields, duplicate keys/IDs, inconsistent
  counts, non-finite numbers and mismatched run/version. Local symlinks are
  rejected. The directory must be operator-owned: these checks do not defend
  against a local attacker racing filesystem changes or changing the process.
- Read-only describes tool effects, not comprehensive data authenticity or
  immunity to malicious model instructions. Remote hosting, authentication for
  multiple users, signed reports, exhaustive history and automated remediation
  are out of scope. Local hosts are responsible for protecting environment secrets.

## Baseline and evidence

Started from research commit `4792d3f0917207b11c76dab0e6ec6f0fbafa5994` on
`feature/mcp-ci-observability`. Core tests passed 107/107 on Python 3.12.13 and
3.10.20 after installing the existing anomaly-test dependency. The research
offline baseline on Windows had 77 passes and five SQLite file-lock cleanup
failures before integration edits; these unrelated sources/tests remain unchanged.
The Linux research workflow supplies a separate regression check.

Live public reader validation retrieved research run
[42463725688](https://github.com/chirayukapoor5/agentshield/actions/runs/42463725688),
which was successful. This is metadata evidence, not a granular test report or
evidence of this feature's CI. Final PR checks and the demonstration transcript
must be consulted for feature validation. No production deployment or paid model
success is claimed.

## References

- [Official MCP v2 installation](https://py.sdk.modelcontextprotocol.io/get-started/installation/)
- [Official in-memory MCP testing](https://py.sdk.modelcontextprotocol.io/get-started/testing/)
- [GitHub workflow-run API](https://docs.github.com/en/rest/actions/workflow-runs)
- [GitHub artifact API](https://docs.github.com/en/rest/actions/artifacts)
