# Architecture overview

The AgentShield platform is structured as a modular SaaS application with separation between API, policy logic, scanning, and data access layers.

- Frontend: Next.js dashboard for monitoring and configuration.
- Backend: FastAPI service with routers for websites, agents, policies, and audit events.
- Persistence: SQLAlchemy models for organizations, users, websites, scans, findings, and reports.
- Security: Authentication, least-privilege policy decisions, audit logging, and SSRF-resistant external scan logic.
- Integration layer: Optional MCP and REST adapters map to the same policy engine.

