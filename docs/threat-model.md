# AgentShield

AgentShield is a modular SaaS platform for AI-agent compatibility and security assessment. The project is designed to help website owners and operators evaluate how AI agents discover, access, and interact with their sites while applying policy controls and monitoring for risky behavior.

## Features

- Website registration and verification workflow.
- Safe compatibility scanning for public websites.
- Persistent findings and score tracking.
- Multi-tenant user and organization model.
- Agent identity and key management.
- Policy engine with dry-run enforcement.
- Audit event log and activity monitoring.
- Optional MCP and REST integration points.
- Responsive SaaS dashboard structure.

## Local development

```bash
cp env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
pytest
uvicorn app.main:app --reload
```

## API docs

Once the backend is running, visit:

- Swagger UI: http://localhost:8000/docs
- OpenAPI JSON: http://localhost:8000/openapi.json

## Architecture notes

- Backend: FastAPI + SQLAlchemy + Pydantic.
- Database: SQLite for local development and tests; Postgres for production.
- Frontend: Next.js app prepared for UI screens.
- Security: JWT auth, tenant scoping, SSRF-safe URL checks, audit logging, and policy enforcement.

## Known limitations

This MVP intentionally focuses on core workflow validity and safe implementation boundaries. It does not claim to fully detect every prompt-injection scenario or guarantee compatibility across arbitrary AI-agent ecosystems. All live integrations and scans require explicit configuration and authorization.

