# AgentShield QA and Security Test Results

**Run date:** 2026-10-29
**Scope:** Existing FastAPI/SQLAlchemy backend, Next.js frontend build, ownership verification, public-site scanning safeguards, evidence persistence, and organization isolation.

## Implementation inspected

- API routes are defined in `backend/app/api/v1/endpoints/`: authentication (`/auth/register`, `/auth/login`, `/auth/me`), websites (registration, verification, scans, findings, website reports), agents, policies, reports, and audit events.
- Persistence models are in `backend/app/models/models.py`: `Organization`, `User`, `Website`, `Scan`, `Finding`, `Report`, `Agent`, and `AuditEvent`.
- Authentication uses OAuth2 password form login and signed JWT bearer tokens in `backend/app/core/security.py`. Protected endpoints resolve the active user and use its organization ID to scope records.
- Backend tests use temporary SQLite databases and FastAPI `TestClient` fixtures in `backend/tests/conftest.py`. Existing and expanded tests are in `backend/tests/test_api.py` and `backend/tests/test_security_scanning.py`.
- Scanner HTTP connections pin the validated DNS address and preserve hostname TLS validation in `backend/app/services/safe_scanner.py`. DNS verification and token lifecycle are handled in `backend/app/services/verification_service.py`.

## Execution summary

| Command/check | Expected result | Actual result | Status | Relevant files |
|---|---|---|---|---|
| `python -m pytest -q --tb=short` from `backend` | All backend tests pass | **46 passed**, 0 failed | PASS | `backend/tests/test_api.py`; `backend/tests/test_security_scanning.py` |
| `npm.cmd run build` from `frontend` | Next.js production build succeeds | Compiled, lint/type checks and static page generation succeeded | PASS | `frontend/package.json`; `frontend/app/page.tsx` |
| `git diff --check` | No whitespace errors | No errors; Git emitted only an LF-to-CRLF notice for `frontend/tsconfig.json` | PASS | Worktree |
| Browser login and pending/empty dashboard | Authenticated data loads; unverified websites cannot scan; empty findings are clear | Login succeeded; dashboard displayed live API websites, pending verification and no findings | PASS (manual) | `frontend/app/page.tsx`; `/api/v1/auth/login`; `/api/v1/websites` |

The test run emitted deprecation warnings for `datetime.utcnow()`, Starlette's `BlockingPortal` alias, and the unset `pytest-asyncio` loop-scope option. These did not fail tests.

## Test results

The actual scanner logic is exercised using deterministic HTTP response fixtures. DNS and socket dependencies are mocked for blocked-address cases. No public or third-party site was contacted.

| Test name | Expected result | Actual result | Pass or fail | Relevant file or endpoint | Security defect discovered | Fix applied |
|---|---|---|---|---|---|---|
| `test_healthcheck`; `test_register_creates_an_isolated_organization` | Health endpoint succeeds; registration creates an isolated organization and supports login | Both assertions passed | PASS | `backend/tests/test_api.py`; `/health`, `/api/v1/auth/register`, `/api/v1/auth/login` | None | None |
| `test_website_registration_returns_txt_challenge_and_never_marks_verified` | New domain stays pending and receives DNS instructions with a challenge | Pending status and challenge instructions were returned | PASS | `backend/tests/test_api.py`; `POST /api/v1/websites` | None | None |
| `test_invalid_dns_txt_does_not_verify_and_records_attempt`; `test_valid_dns_txt_verifies_once_and_clears_stored_token`; `test_expired_dns_token_is_invalidated_and_audited`; `test_dns_verification_attempts_are_rate_limited`; `test_verification_dns_outage_is_reported_without_consuming_attempt` | Only matching, unexpired DNS TXT token verifies; reuse/expiry/incorrect values are rejected; retry limits apply; DNS outage is reported | All passed. Stored value was a hash; success cleared the challenge; response, captured logs and audit events did not contain the challenge token | PASS | `backend/tests/test_security_scanning.py`; `/api/v1/websites/{id}/verify` | None observed | No runtime change required; added token leak assertions |
| `test_scan_is_rejected_until_dns_ownership_is_verified`; `test_protected_workflows_require_authentication`; `test_unverified_website_has_an_empty_scan_history` | Reject pre-verification scans and unauthenticated access; return empty history before scans exist | 403, 401 and empty scan history expectations passed | PASS | `backend/tests/test_api.py`; website scan, verification and findings routes | None | None |
| `test_verified_scan_persists_actual_evidence_and_report` | Run actual check logic over controlled responses; persist check evidence, findings, scan IDs, and report data | Passed. The scanner detected the intentionally absent header in fixture HTTP responses and persisted matching evidence and report output | PASS | `backend/tests/test_api.py`; `/api/v1/websites/{id}/scans`, findings, `/api/v1/reports/{id}` | None observed | Replaced the prior scanner-result stub with a controlled fetcher so this test exercises actual check generation and persistence |
| `test_scanner_generates_only_evidence_backed_findings_and_unavailable_checks`; `test_unavailable_hostname_never_creates_a_fabricated_finding`; `test_http_error_is_recorded_as_unavailable_not_an_html_finding` | Generate only findings supported by observed responses; avoid interpreting unavailable/error responses as findings; do not retain exposed candidate secret values | Passed. Evidence came from fixture responses; candidate secret value was absent from persisted finding evidence; unavailable cases generated no invented findings | PASS | `backend/tests/test_security_scanning.py`; `backend/app/services/safe_scanner.py` | None observed | None |
| `test_failed_scan_is_persisted_without_claiming_success`; `test_scan_with_no_evaluable_checks_is_persisted_as_failed` | Failed/unassessable scans are not marked completed and have no misleading score | Both passed; no-evaluable-check scan persisted as failed with null scores and unavailable checks | PASS | `backend/tests/test_security_scanning.py`; `POST /api/v1/websites/{id}/scans` | Correct status behavior is essential; the all-unavailable case is now explicitly regression-tested | Added regression coverage; `backend/app/services/scan_service.py` records the all-unavailable result as failed |
| `test_dns_resolution_blocks_non_public_ipv4_and_ipv6` (9 address cases); `test_dns_resolution_rejects_mixed_public_and_private_answers` | Reject localhost, private, link-local, metadata, reserved and IPv6 local/mapped answers; reject mixed public/private DNS answers | Every case was rejected | PASS | `backend/tests/test_security_scanning.py`; scanner DNS validation | None observed | None |
| `test_prohibited_dns_answers_are_blocked_before_socket_creation` (10 address cases); `test_private_dns_answer_never_reaches_a_controlled_local_server` | Prohibited DNS must be rejected before socket creation or an HTTP request to the controlled local server | All blocked-address cases passed; socket spy observed zero calls and the local server handled zero requests | PASS | `backend/tests/test_security_scanning.py`; `SafeFetcher.get` and DNS validation | No prohibited destination was contacted in these controlled tests | Added explicit pre-connection assertions and a local listener test |
| `test_pinned_fetcher_revalidates_same_host_redirect_and_caps_bytes`; `test_pinned_fetcher_does_not_follow_redirect_to_metadata_ip`; `test_dns_rebinding_to_private_ip_is_blocked_on_redirect`; `test_pinned_fetcher_surfaces_timeout`; `test_pinned_http_connection_connects_to_the_validated_ip` | Revalidate redirect DNS, block prohibited redirect targets and rebinding, cap bytes, surface timeouts, and connect only to validated IP | All passed using mocked DNS/socket/HTTP responses; oversized response was truncated to the configured per-call limit | PASS | `backend/tests/test_security_scanning.py`; `SafeFetcher`, pinned HTTP/TLS connections | None observed | None |
| `test_website_urls_must_be_public_dns_origins` | Reject non-HTTP(S), private/IP-literal, path-bearing, and nonstandard-port registration targets | All invalid origins returned 422 | PASS | `backend/tests/test_api.py`; `POST /api/v1/websites` | None observed | None |
| `test_cross_tenant_resources_are_not_accessible` | Tenant B cannot read or scan Tenant A website, findings, reports, agents, or linked policy; audit data is scoped | All tested cross-tenant requests were denied/not found; Tenant B received no Tenant A audit events | PASS | `backend/tests/test_security_scanning.py`; websites, scans, findings, reports, agents, policies and audit routes | None observed in tested paths | None |

## Log and sensitive-data inspection

- The successful DNS verification test checks the raw token is absent from the verification response, captured application logs, and returned audit records.
- The scanner fixture test checks that a credential-like value observed in a public configuration response is not copied into finding evidence.
- The scanned application does not currently emit scan response bodies or verification tokens through explicit `print`/logger calls found in the inspected backend source. This is a source and test-capture check, not a centralized production log audit.

## Remaining risks and untested features

- No real public website was scanned; live DNS propagation and real TLS certificate behavior were not exercised.
- DNS rebinding and redirect cases were simulated with mocks. The controlled local server test verifies that a prohibited DNS answer is blocked before any connection; it does not simulate production network routing.
- No production egress firewall or isolated scanner worker was configured. The scanner still executes synchronously in the API process.
- Ownership is established at verification time and is not continuously rechecked. File-based verification is not implemented.
- Tests do not exercise high-concurrency load, production-scale timeout behavior, actual TLS certificate failures, or every URL-parser edge case.
- Frontend validation included production build and a manual browser login/pending/empty-state check; no dedicated frontend unit or end-to-end automation suite was run.
- Existing datetime and pytest-asyncio deprecation warnings remain.
