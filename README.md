# AgentShield

## Try the AgentShield Guard showcase

The new [standalone interactive product demo](public-demo/index.html) lets developers compare a registered AgentShield guard against an unwrapped tool path in five synthetic scenarios. It includes a guided walkthrough, an SDK snippet, and a route to real developer feedback.

**Published and verified (November 7, 2026): [Try the live AgentShield Guard demo](https://chirayukapoor5.github.io/agentshield/).** GitHub Pages deployment [#42362092218](https://github.com/chirayukapoor5/agentshield/actions/runs/42362092218) passed the build, SDK-style browser replay checks, publication and unauthenticated HTTPS verification (HTTP 200, containing demo and feedback sections). The release entrypoint is `.github/workflows/nextjs.yml` on `main`, which checks out `public-demo/` from this research branch and publishes only the standalone static demo.

- [Download the independently verified static preview](https://github.com/chirayukapoor5/agentshield/actions/runs/42359471308/artifacts/13569255940) (GitHub Actions artifact).
- [View and contribute developer feedback](https://github.com/chirayukapoor5/agentshield/issues/2) — no external input has been claimed yet.
- [60-second walkthrough and launch checklist](docs/SHOWCASE_LAUNCH.md).

This is a deterministic SDK policy demonstration, **not** a live model-security test or measured AgentDojo attack-success rate.

AgentShield is a prototype for owner-authorized website compatibility and security checks. It combines a FastAPI backend, SQLAlchemy persistence, Alembic migrations, and a Next.js dashboard.

> **Project status:** prototype. Ownership is verified through a DNS TXT challenge before scanning. The scanner makes bounded, non-destructive public HTTP(S) requests and persists evidence for the checks it implements. It is not a penetration test, security certification, or guarantee that a site is safe.

## AgentShield Guard — one-package protective SDK prototype

A new self-contained Python SDK wraps application-owned agent tools with explicit allowlists, approval gates, exact HTTPS hostname rules and fail-closed denial. Install directly from this checkout (not yet published to PyPI):

```bash
python -m pip install ./sdk
python sdk/examples/quickstart.py
python sdk/examples/demo_stats.py
```

Source: [sdk/](sdk/) · [documentation](sdk/README.md) · [reproduced local demo](docs/SDK_DEMO_RESULTS.md).

**Current limitation:** The application must register the SDK's wrapped functions for enforcement; this is not an automatic universal agent firewall. Synthetic policy decisions are **not** AgentDojo ASR or real-world prompt-injection efficacy. The SDK now has a bounded optional Groq transport and an OpenAI-compatible local function-call dispatcher. Signed policies, proxy interception, automatic framework interception and independent production security certification are not implemented.

---

## Read-only MCP CI intelligence

The [MCP integration](integrations/mcp_ci/) lets a local MCP host inspect real GitHub Actions runs for `chirayukapoor5/agentshield` on `research/multilingual-injection-2026` and read sanitized local test summaries. It uses the official MCP Python SDK v2, strict typed inputs, bounded outputs, and the existing AgentShield authorization guard for every tool. The default transport is **stdio**, with no public endpoint.

| Tool | Purpose |
| --- | --- |
| `list_ci_runs` | List recent runs for an allowlisted workflow |
| `get_ci_run` | Read run/job outcomes and failed step numbers |
| `get_test_summary` | Read sanitized test counts and duration |
| `list_failed_tests` | List bounded, hashed failure/error identifiers |

From the repository root, create a separate Python 3.12 environment:

```powershell
py -3.12 -m venv .venv-mcp
.venv-mcp\Scripts\Activate.ps1
python -m pip install ./sdk './integrations/mcp_ci[test]'
python -m agentshield_mcp_ci
```

On Linux/macOS, create it with `python3.12 -m venv .venv-mcp` and activate with `source .venv-mcp/bin/activate`. Configure your MCP host to launch that environment's Python with `-m agentshield_mcp_ci`.

Run tests or a demonstration separately:

```bash
python -m pytest -q integrations/mcp_ci/tests
python integrations/mcp_ci/examples/ci_triage_demo.py --offline
python integrations/mcp_ci/examples/ci_triage_demo.py --live
```

Offline mode exercises all four tools through a real MCP client and labels synthetic data with `is_fixture=true`. Live mode reads actual GitHub metadata without substituting fixtures. Public metadata needs no credentials; optional `GITHUB_TOKEN` credentials should grant only Actions:read for this repository. To serve operator-verified local JSON reports, set `AGENTSHIELD_REPORT_DIR`; report filenames are `run-RUN_ID-py-VERSION.json`.

**Verified implementation results (November 14, 2026, commit `a571e028abb57c70d11b6ae9209c44564b06f784`):** 78 integration tests passed, including in-memory and subprocess stdio protocol tests; all 107 core SDK tests passed on both Python 3.10 and 3.12. [MCP CI](https://github.com/chirayukapoor5/agentshield/actions/runs/43579313025), [SDK CI](https://github.com/chirayukapoor5/agentshield/actions/runs/43579313021), and [research CI](https://github.com/chirayukapoor5/agentshield/actions/runs/43579313073) passed. Four sanitized JSON artifacts were verified across those runs, including separate SDK matrix versions.

**Limits:** automatic remote artifact ZIP retrieval is unsupported; missing local reports return `report_unavailable`. CI uploads sanitized JSON only, without raw JUnit, logs or tracebacks. Local report provenance must be verified by the operator. The optional bounded Groq model demo is manual opt-in and fixture-only; its mocked tests do not establish real-model success. Remote hosting, production readiness and general prompt-injection protection are not claimed. Core SDK Python 3.10 support is unchanged.

See the [setup guide, schemas, report pipeline and threat model](docs/MCP_CI_INTEGRATION.md) and [implementation PR](https://github.com/chirayukapoor5/agentshield/pull/3).

---

## Research track: multilingual adaptive prompt injection (November 2026)

The original AgentShield SaaS remains a **website-scanning prototype**. A separate, experimental research package lives in [research/README.md](research/README.md). Its analysis plan is in [docs/ANALYSIS_PLAN.md](docs/ANALYSIS_PLAN.md). No full AgentDojo attack evaluations or per-language ASR comparisons have been published, and no measured attack-success rates or task-utility results are claimed. The bounded Groq tool-use smoke is separate from AgentDojo benchmarking.

The research comparisons are C1 static English, C2 static translated, C3 adaptive English-only, and C4 adaptive multilingual/script/code-mix, using a single pinned AgentDojo suite and official checkers. The repository defaults to a zero-network mock client.

```bash
python -m pip install pytest 'PyYAML>=6.0.1,<7'
make test
make dry-run
```

Install the pinned AgentDojo package with `make setup` only in an environment where package downloads are permitted. Fill `config/api.yaml` and private `.env` before any paid calls; provider `mock` makes no real API calls. `scripts/check_api.py` is manual opt-in only. The official integration is incomplete; the scripts fail closed rather than producing fabricated scores. See [research/API_INTEGRATION.md](research/API_INTEGRATION.md) and [docs/RESULTS_SUMMARY.md](docs/RESULTS_SUMMARY.md).

---

## What is implemented

- JWT-based user registration, login, and current-user endpoint.
- Organization-scoped website and agent API operations.
- Organization-scoped website registration and DNS TXT ownership challenges.
- Safe public HTTP(S) checks with IP pinning, redirect validation, and response/time/request limits.
- Evidence-backed scan checks, findings, timestamps, scanner version, and transparent check-coverage scores.
- Policy creation and listing endpoints.
- Audit-event listing and JSON report generation.
- FastAPI OpenAPI documentation.
- A Next.js dashboard with sign-in, organization-scoped website/agent/finding/audit data, and website registration.
- A local, read-only MCP CI interface with four guarded tools, sanitized test-report exports and protocol/security tests.

## Current limitations

- DNS verification proves control of the configured hostname at the time of the challenge. It does not verify control of every related domain or prevent later DNS changes.
- The scanner evaluates a small set of public checks (HTTPS/TLS, selected headers, common discovery paths, basic HTML semantics, and common configuration paths). It does not authenticate, execute JavaScript, crawl a site, exploit issues, or detect all secrets/risks.
- Scores are deterministic summaries of only the available implemented checks. They are not overall security ratings; unavailable checks are excluded and coverage is displayed.
- The scanner must still be deployed in an environment with network egress restricted to public destinations. Application-level checks do not replace infrastructure egress controls.
- The dashboard loads organization-scoped websites, agents, scans, findings, and audit events. Agent request telemetry, alerts, and live policy enforcement are not implemented.
- Existing pre-migration verification flags are reset because they were not backed by proof. Old synthetic scan records and findings are excluded from current scan and finding views.
- Remote MCP hosting, automatic remote test-artifact retrieval and a website-scanning MCP interface remain unimplemented. The local CI interface is described above.
- Production authentication hardening, background scan jobs, CI security scanning, and independent security review remain incomplete.
- The demo account and development credentials are for local use only. Replace secrets and credentials before any deployment.

## Requirements

- Python 3.12+
- Node.js 20+
- npm
- Docker Desktop (optional, for the Compose setup)

## Run locally

### Backend

In PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Set-Location backend
python -m alembic upgrade head
python -m app.db.init_db
python -m uvicorn app.main:app --reload
```

The backend uses SQLite by default for local development. Migrations are required for an existing database; they preserve existing website records but reset unproven verification flags. From a separate terminal, run the tests:

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location backend
python -m pytest
```

### Frontend

From the repository root, open another terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open <http://localhost:3000> for the dashboard. Sign in with the local demo account (`demo@agentshield.local` / `password123`) or another API account. Register a root website origin, publish the returned token as the TXT value at `_agentshield-challenge.<hostname>`, then verify ownership from the dashboard. Tokens expire after 60 minutes by default, and five failed DNS checks trigger a 15-minute lockout. Once verified, run a safe scan and review check evidence, unavailable checks, findings, score coverage, and scan time. The dashboard token is stored in session storage for the current browser tab.

### Docker Compose

From the repository root:

```powershell
Copy-Item env.example .env
docker compose up --build
```

The Compose configuration starts PostgreSQL, Redis, the API, and the dashboard. The API container runs database migrations before startup. Redis is reserved for future background-work integration and is not currently used by the API.

## API

With the backend running:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Health check: <http://localhost:8000/health>

API routes are served under `/api/v1`:

| Area | Routes |
|---|---|
| Authentication | `/auth/register`, `/auth/login`, `/auth/me` |
| Websites | `/websites`, `/websites/{id}/verification`, `/verify`, `/scans`, `/findings`, and `/reports` |
| Agents | `/agents` and agent detail/key lifecycle routes |
| Policies | `/policies` |
| Audit | `/audit-events` |
| Reports | `/reports` |

The development database seed command creates `demo@agentshield.local` / `password123`. Use it only for local development; remove the seed account and replace development secrets before deployment.

## Repository map

```text
backend/
  app/
    api/v1/endpoints/  # HTTP routes
    core/              # Settings and authentication
    db/                # SQLAlchemy session and initialization
    models/            # Persistent data models
    services/          # Scan, policy, and report logic
  tests/               # Backend API tests
frontend/
  app/                 # Next.js dashboard preview
docs/                  # Architecture, deployment, and threat-model notes
```

## Suggested next steps

1. Move scans to an isolated, egress-restricted background worker with cancellation and job-level quotas.
2. Add controlled network integration tests for the pinned HTTP/TLS transport and operational monitoring for scanner failures.
3. Implement policy enforcement, agent credential lifecycle, activity telemetry, and alerts.
4. Add account recovery, stronger production session handling, CI security/dependency/container checks, and operational hardening.

## License

MIT. See [LICENSE](./LICENSE).
