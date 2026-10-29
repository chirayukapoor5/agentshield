# Architecture overview

- **Frontend:** Next.js dashboard for authentication, website ownership challenges, scan status, check evidence, findings, and audit history.
- **API:** FastAPI with versioned authentication, website, agent, policy, report, and audit routes.
- **Persistence:** SQLAlchemy models with Alembic migrations; SQLite is the local default, and PostgreSQL is supported by Compose.
- **Ownership:** Random DNS TXT challenge values are returned once and stored as hashes. Scans are denied until the server confirms the TXT value.
- **Scanner:** Synchronous safe scanner using DNS validation, pinned-IP HTTP connections, hostname-checked TLS, same-host redirect handling, HTML parsing without script execution, and bounded request/response resources.
- **Evidence:** Scan records persist checks, findings, timestamps, scanner version, scores, and score coverage. Old prototype scan rows have no scanner version and are excluded from current scan views.
- **Audit:** Organization-scoped events record registration, verification, scanning, report generation, agent changes, and policy creation.

Scores are unweighted averages across applicable checks: a passed check contributes 1, a finding contributes 0, and unavailable checks are excluded. Compatibility uses page metadata/semantics, sitemap, robots, OpenAPI discovery, and the limited agent-readiness indicator. Security uses HTTPS availability, HTTP-to-HTTPS behavior, certificate validation, selected response headers, and common public configuration paths. The returned coverage count identifies how many of those checks were evaluable. Scores summarize this subset only; they are not overall security ratings.

## Current boundaries

- DNS TXT ownership challenge only; the verification proof needs to be configured by the domain operator.
- No authenticated or active vulnerability testing, JavaScript execution, deep crawl, or security certification.
- The scanner is synchronous and process-local; use an isolated worker with enforced network egress controls before production deployment.
- Agent activity ingestion, enforced policy decisions, remote MCP, scheduled scans, and production account lifecycle are not implemented.
