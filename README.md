# AgentShield

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
