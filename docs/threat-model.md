# AgentShield threat model (prototype)

## Protected assets

- Website ownership challenge hashes and the verification state.
- Organization-scoped website, scan, finding, report, agent, policy, and audit records.
- Application credentials, database records, and scan worker network access.

## Trust boundaries and controls

- Authentication is bearer-token based. Every website, finding, scan, report, agent, policy, and audit query is scoped to the authenticated user's organization.
- A website is not considered verified from registration or a client boolean. A random 256-bit DNS TXT value is returned once, only its SHA-256 hash is stored, the value expires, and failed attempts are persisted and locked out.
- A scan is rejected unless the website's server-side ownership state is verified. Website URLs are restricted to DNS hostnames and standard HTTP(S) ports.
- Scanner DNS answers are validated as public addresses and the HTTP connection is opened directly to one of those validated IPs. TLS still validates the original hostname and uses it as SNI. Redirects are limited to the verified hostname and are validated/resolved again.
- The scanner uses GET only, does not execute JavaScript, and limits response bytes, request count, redirects, per-request duration, and process-local concurrency. Findings retain evidence without retaining detected configuration values.
- Scan checks distinguish `passed`, `finding`, and `unavailable`; unavailable checks are excluded from deterministic scores. Scores are limited to implemented checks and are not security certifications.
- Verification, scan, report, agent, policy, and registration actions write organization-scoped audit events without recording challenge tokens or response secrets.

## Threats considered

| Threat | Mitigation | Remaining limitation |
|---|---|---|
| Forged ownership / direct scan API call | DNS TXT challenge; backend checks verification state before scan | Ownership can change after verification; owners should keep control of registered domains |
| Token guessing or replay | Cryptographically random token, hash-only storage, expiration, consumed on success, failed-attempt lockout | Token issuance and API authentication need production-grade rate limiting and monitoring |
| SSRF to localhost, private networks, cloud metadata, IPv6 local ranges | Reject non-global DNS answers and IP literals; connect to pinned numeric address; do not follow cross-host redirects | Network egress firewalling is still required; deployments must block private, link-local, metadata, and internal service ranges |
| DNS rebinding / redirect abuse | Resolve and validate each hop; use that validated IP for the socket; restrict redirects to same verified hostname | DNS libraries and host networking remain in the trusted computing base |
| Oversized, slow, malformed remote response | Bounded response reading, network timeout, request budget, safe parser, explicit unavailable status | This is synchronous prototype work, not an isolated worker or durable job queue |
| Cross-tenant IDOR | Organization filters at every resource lookup and relationship validation for policy website references | More negative tests are needed as new resource endpoints are added |
| False security claims | Evidence-backed check results, confidence/status fields, legacy synthetic data excluded, coverage shown | Checks are intentionally narrow and may miss vulnerabilities or misclassify site-specific behavior |

## Explicitly out of scope

- Exploitation, credential testing, authentication bypass, arbitrary command execution, or destructive testing.
- Scanning private or internal targets, bypassing access controls, or following redirects to unrelated hosts.
- Guaranteeing protection from prompt injection or certifying AI-agent compatibility.

## Deployment requirements

Run the API scanner in a dedicated worker/container with egress restricted at the network layer to public web destinations on ports 80 and 443. Deny loopback, RFC1918, link-local, unique-local IPv6, cloud metadata, cluster control planes, databases, and internal services. Use TLS, a strong secret key, a production database, request rate limiting, dependency/container scans, and log retention/redaction controls before exposing the service publicly.
