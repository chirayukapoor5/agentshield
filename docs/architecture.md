# Threat model

AgentShield assumes that public inputs such as websites, agent tool output, and remote content may be malicious, misleading, or adversarial. The platform therefore uses a defense-in-depth approach:

1. Treat retrieved content as untrusted input.
2. Validate and constrain all URLs before external access.
3. Run scans with request and content limits.
4. Require authenticated, tenant-scoped access to sensitive resources.
5. Deny unsafe network destinations by default.
6. Log decisions and audit events for every privileged action.
7. Require human approval for high-impact changes.

## Key protections

- SSRF-safe checks for localhost, private networks, and reserved addresses.
- Policy-based access decisions with trace IDs.
- Tenant isolation on org resources.
- Audit logging for access, scanning, and security policy decisions.
- Safe error handling that avoids leaking internal data.

