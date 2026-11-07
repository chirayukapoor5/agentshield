# AgentShield public showcase launch runbook
Last checked: 2026-11-07. Scope: **static interactive product demonstration**, not a live LLM or production security certification.

**Public demo (verified): https://chirayukapoor5.github.io/agentshield/** — Default-branch [deployment run #42362092218](https://github.com/chirayukapoor5/agentshield/actions/runs/42362092218) deployed successfully. GitHub Actions then fetched the public HTTPS URL unauthenticated, observed HTTP **200**, and checked that `id="demo"` and `id="feedback"` are in the served HTML at 2026-11-07 10:01 UTC. Browser interaction tests passed in a simulated DOM; a manual mobile-browser usability review is still recommended.

## Current status and verified evidence

- `public-demo/index.html` is a zero-dependency interactive static page with 5 synthetic tool requests, guarded/unguarded comparison, a guided replay, SDK code example, and an explicit GitHub issue feedback flow.
- `scripts/verify_public_demo.py` checks expected sections, safety language, no external JavaScript, missing anchors, JavaScript syntax and secret placeholders.
- `scripts/test_public_demo.mjs` simulates UI actions in a local DOM stub and verifies the protected/unguarded behavior, browser trace flags, and GitHub feedback draft URL.
- Verified GitHub Actions build: [showcase workflow #42359471308](https://github.com/chirayukapoor5/agentshield/actions/runs/42359471308) — static/JavaScript checks and UI smoke tests passed; deploy job skipped on the PR event.
- Archive of the passing static build: [preview artifact](https://github.com/chirayukapoor5/agentshield/actions/runs/42359471308/artifacts/13569255940).
- Initial **push** deployment attempt failed before Pages was configured. The issue was resolved after selecting **GitHub Actions** in repository Pages settings and replacing the incorrect root-level Next.js workflow with the standalone static showcase publisher on `main`.
- Public developer feedback thread: [GitHub issue #2](https://github.com/chirayukapoor5/agentshield/issues/2). At creation it had **0 external responses**.

## If future Pages deployments fail (one-time admin setup already completed)

1. Open [AgentShield Settings → Pages](https://github.com/chirayukapoor5/agentshield/settings/pages).
2. Under **Build and deployment → Source**, choose **GitHub Actions**. Save.
3. Go to [Actions → publish-agent-shield-showcase](https://github.com/chirayukapoor5/agentshield/actions/workflows/publish-showcase.yml). Use **Run workflow** on branch `research/multilingual-injection-2026`, or rerun the failed push workflow.
4. Confirm **build** and **deploy** both succeeded. The deployment job must report a `page_url`; build-only success does not imply public access.
5. Visit the expected repository Pages URL: `https://chirayukapoor5.github.io/agentshield/`. Treat that address as **expected, not verified live** until an unauthenticated HTTPS request and an interactive browser test succeed.

Pages is now enabled and the actual site has been verified live. Do **not** add a repository-administration personal access token to fix a deployment. GitHub's default `GITHUB_TOKEN` cannot enable a Pages site on its own.

### Post-publication smoke checklist

- Open the HTTPS page in a private/incognito browser and on a mobile-width viewport.
- Choose **Send an email**, then **Without AgentShield**, then **Run**. Expect `outside_policy_boundary` and `handler_executed: false`. This does not mean an actual unguarded handler ran.
- Switch **With AgentShield**, run again, and expect `denied` and `approval_not_configured`. No actual email should be sent.
- Choose **Read a document**, run in guarded mode, expect `allowed` but `handler_executed: false` (static replay).
- Use **Guided walkthrough** and ensure the mode changes.
- Fill the feedback form using **non-sensitive sample text**; confirm it opens a new GitHub issue draft, but do **not** click Submit merely for a test. Also verify direct [feedback discussion](https://github.com/chirayukapoor5/agentshield/issues/2) is accessible.
- On success, record the **exact URL, HTTP status, UTC verification time, workflow run number and browser test outcome** below.

Public URL: **https://chirayukapoor5.github.io/agentshield/**  
HTTP result: **200, confirmed by unauthenticated curl inside GitHub Actions at 2026-11-07 10:01 UTC**  
Live deployment run: **[#42362092218](https://github.com/chirayukapoor5/agentshield/actions/runs/42362092218)**  
External user feedback count: **0 confirmed at issue creation**

## 60-second live walkthrough script

**0–10 seconds:** “A tool-using AI agent may read untrusted text, but the dangerous step is when that text influences a privileged tool call. AgentShield puts an authorization check at that boundary.”

**10–23 seconds:** Select **Send an email** and **Without AgentShield**. Run: “An unwrapped function is outside our SDK's enforcement boundary. This browser does not execute tools; it illustrates the risk of not registering the wrapper.”

**23–40 seconds:** Switch **With AgentShield**, run again: “This tool requires approval. With no approval callback, the policy denies it before the handler runs. This is enforced by the Python SDK's explicit tool registry, not by claiming the model ignores the attack.”

**40–50 seconds:** Select **Read a document** and run: “Authorized read-only actions can still be allowed.”

**50–60 seconds:** Scroll to the SDK snippet and feedback: “If your agent can email, write files, or call external APIs, tell us your stack and the integration blocker. We need real developer evidence before claiming market demand.”

Do not call this a real attacker success/failure benchmark. It is a product policy-boundary demonstration with testable behaviors.

## Real developer feedback experiment

Target 20 **qualified** developers using LangGraph, OpenAI Agents SDK, CrewAI, AutoGen or custom Python agents. Share the verified live link, with a short request to spend five minutes comparing the two modes. Ask for:
- The real agent framework and authorization-sensitive tool they use
- Whether explicit approval or host allowlists already exist
- Their top integration blocker
- Whether they would test an integration on their own synthetic sandbox in the next month

Track *unique external replies* on issue #2 or independent feedback issues; do not count the team's posts, page views, reactions, or generated example form submissions as market validation. Avoid contacting strangers repeatedly or automatically. Private outreach should be consent-aware and personal rather than bulk messaging.

Suggested early gates (goals, **not results**): 20 qualified developers approached; 10 demo interactions confirmed; at least 5 substantive responses; 3 genuine trial volunteers; 1 completed sandbox integration. If few people attempt an integration, revisit onboarding and framework support before building more research features.

## Deployment fallback

The [Vercel](https://vercel.com/) app is an alternate direct hosting provider for a public web deployment. Connecting Vercel requires explicit account authorization. Its connection is *not* confirmed in this repository, so no Vercel URL or deployment is claimed.

## Product limits

The SDK protects registered Python tool handlers, not arbitrary model output, unwrapped functions, DNS rebinding/redirect behavior of arbitrary external handlers, or every framework by default. The static showcase runs no model, code executor or remote tools, and does not measure multilingual prompt-injection ASR. Those research experiments remain separate and incomplete.
