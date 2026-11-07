# AgentShield

## Public AgentShield Guard demo

**Live:** [https://chirayukapoor5.github.io/agentshield/](https://chirayukapoor5.github.io/agentshield/)

The standalone showcase now executes **all five synthetic tool workflows** in a safe in-memory sandbox: read a document, approve/deny an email, approve/deny file deletion, check an exact HTTPS host against an allowlist, and approve a toy command. The guided tour shows the result of each step; nothing uses the real network, operating system or email delivery. It includes an audit trail, reset button and developer feedback form.

To validate the same five categories against the **actual Python Guard SDK**, run [`sdk/examples/five_stage_guard_demo.py`](https://github.com/chirayukapoor5/agentshield/blob/research/multilingual-injection-2026/sdk/examples/five_stage_guard_demo.py). The [latest verified public release #42372135342](https://github.com/chirayukapoor5/agentshield/actions/runs/42372135342) passed real Chromium desktop/mobile acceptance tests **against the live HTTPS website**; the page and bundled JavaScript both returned HTTP 200.

## Get AgentShield into a real LangGraph agent

The optional [LangGraph ToolNode adapter](https://github.com/chirayukapoor5/agentshield/blob/research/multilingual-injection-2026/sdk/agentshield_guard/langchain_tools.py) wraps synchronous LangChain tools in AgentShield's authorization gate. Use the **wrapped** definitions in ToolNode **and** `model.bind_tools`; using original tool objects bypasses the guard.

```bash
git clone https://github.com/chirayukapoor5/agentshield.git
cd agentshield
git checkout research/multilingual-injection-2026
python -m pip install -e './sdk[langgraph]'
python sdk/examples/langgraph_toolnode.py
```

This executable example invokes a real compiled LangGraph `ToolNode` using fictional inputs, with one authorized read, one approved simulated email, and denied unauthorized calls. It needs no API key. The adapter does not support injected ToolRuntime arguments, async-only tools, or handlers that bypass the wrapped registry. [SDK limitations and tests](https://github.com/chirayukapoor5/agentshield/blob/research/multilingual-injection-2026/sdk/README.md).

A separate [bounded Groq live-model canary on November 7](https://github.com/chirayukapoor5/agentshield/actions/runs/42369186158) successfully executed **one model-generated `read_note` tool call** in two provider turns. The real model did not attempt an email call; this must **not** be presented as an attack-success-rate or prompt-injection-resistance result. See [evidence and limitations](https://github.com/chirayukapoor5/agentshield/blob/research/multilingual-injection-2026/docs/LIVE_MODEL_CANARY_2026-11-07.md).

**Verified security engineering scorecard:** [SDK CI #42371831449](https://github.com/chirayukapoor5/agentshield/actions/runs/42371831449) passed **90/90 automated tests on Python 3.10 and 3.12**. The deterministic [10,000-case stress CI #42371796465](https://github.com/chirayukapoor5/agentshield/actions/runs/42371796465) passed **10,000/10,000 per Python version**, across malformed model tool calls, URL allowlists, approvals/audit failures, unlisted tool names, and international input preservation. The public demo's **5/5 synthetic UI stages** also passed. These measure **engineering contract correctness, not real-world prompt-injection prevention**; official held-out multilingual attack-success rate (ASR) remains **N/A**. See [full 10k case breakdown](https://github.com/chirayukapoor5/agentshield/blob/research/multilingual-injection-2026/docs/STRESS_10K_REPORT.md) and [scoring methods](https://github.com/chirayukapoor5/agentshield/blob/research/multilingual-injection-2026/docs/SCORING_METHODOLOGY.md).

The current Guard SDK and research code are on branch [research/multilingual-injection-2026](https://github.com/chirayukapoor5/agentshield/tree/research/multilingual-injection-2026); [developer feedback is welcome in issue #2](https://github.com/chirayukapoor5/agentshield/issues/2).

This is a **policy-boundary simulation**, not a live attack, measured multilingual defense efficacy, or production security guarantee.

AgentShield is a prototype for owner-authorized website compatibility and security checks. It combines a FastAPI backend, SQLAlchemy persistence, Alembic migrations, and a Next.js dashboard.

> **Project status:** prototype. Ownership is verified through a DNS TXT challenge before scanning. The scanner makes bounded, non-destructive public HTTP(S) requests and persists evidence for the checks it implements. It is not a penetration test, security certification, or guarantee that a site is safe.

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

## Current limitations

- DNS verification proves control of the configured hostname at the time of the challenge. It does not verify control of every related domain or prevent later DNS changes.
- The scanner evaluates a small set of public checks (HTTPS/TLS, selected headers, common discovery paths, basic HTML semantics, and common configuration paths). It does not authenticate, execute JavaScript, crawl a site, exploit issues, or detect all secrets/risks.
- Scores are deterministic summaries of only the available implemented checks. They are not overall security ratings; unavailable checks are excluded and coverage is displayed.
- The scanner must still be deployed in an environment with network egress restricted to public destinations. Application-level checks do not replace infrastructure egress controls.
- The dashboard loads organization-scoped websites, agents, scans, findings, and audit events. Agent request telemetry, alerts, and live policy enforcement are not implemented.
- Existing pre-migration verification flags are reset because they were not backed by proof. Old synthetic scan records and findings are excluded from current scan and finding views.
- An MCP server/tool interface is not implemented yet.
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
