# Local and prototype deployment

## Requirements

- Python 3.12+
- Node.js 20+
- Docker Desktop only when using Compose

## Run locally (PowerShell)

From the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Set-Location backend
python -m alembic upgrade head
python -m app.db.init_db
python -m uvicorn app.main:app --reload
```

In another terminal:

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run dev
```

The local database is SQLite. The development seed account is `demo@agentshield.local` / `password123`; never use it outside local development.

## Docker Compose

```powershell
Copy-Item env.example .env
docker compose up --build
```

The API container applies Alembic migrations before starting. Configure a unique, long random `SECRET_KEY` and a production `DATABASE_URL` before using any non-local deployment.

## Scanner egress requirements

Application-level IP validation is defense in depth, not a network perimeter. Place scanning in an isolated worker/container and enforce firewall or cloud network rules that deny loopback, private, link-local, unique-local IPv6, metadata, cluster, database, and other internal destinations. Permit only public DNS resolution and outbound TCP to ports 80 and 443. Do not mount credentials or internal service tokens in the scanner environment.

The current scanner runs synchronously in the API process. It is not designed for high concurrency, long-running scans, or production workload isolation. A dedicated restricted worker, durable queue, per-tenant quotas, cancellation, and monitoring are required before production.

## Backups and operations

- Back up the database before applying schema changes.
- Run `python -m alembic upgrade head` before deploying new application code.
- Monitor API and scanner failure rates without logging challenge tokens or remote response bodies.
- Rotate the JWT secret and other credentials using a secrets manager.
- Use HTTPS, restricted CORS origins, database access controls, retention limits, and dependency/container vulnerability checks.

The current project does not include production CI, observability, a scan queue, or a full backup/restore procedure.
