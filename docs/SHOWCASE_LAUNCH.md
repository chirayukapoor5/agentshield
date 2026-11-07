# AgentShield public showcase launch runbook

Checked: 2026-11-07. **Public functional demo v3:** https://chirayukapoor5.github.io/agentshield/

The earlier v2 [deployment run #42363097365](https://github.com/chirayukapoor5/agentshield/actions/runs/42363097365) passed build, deploy and HTTP verification. V3 requires a separate successful run of the Chromium release gate before it should be called publicly verified. The public page and bundled `sandbox.js` independently returned **HTTP 200**; the deployed JavaScript contained the one-time approval implementation. The CI test uses a simulated DOM; independent interactive-browser verification from this environment is blocked by network restrictions.

This is a **synthetic JavaScript tool sandbox** demonstrating SDK-equivalent decisions, not a live Groq/LLM run or an actual execution of the Python AgentShield SDK.

## Five complete demo phases (v3)

The interactive page now includes a real *fictional in-memory effect* for each of the five cases. Every step has guarded and unguarded comparisons, readable handler results and a resettable audit log. No operating-system command, external HTTP request, email delivery or real file deletion is performed.

| Stage | Guarded default | How to permit / effect shown |
| --- | --- | --- |
| 1. Read a document | Allowed immediately | Runs the synthetic document reader and increments Document reads |
| 2. Send email | Denied pending human review | Select **Reviewer approves ONE synthetic action**; a fictional email enters the outbox; approval automatically resets |
| 3. Delete file | Denied pending human review | Explicitly approve once; the sample file becomes **Deleted (sandbox)**; Reset restores it |
| 4. Fetch a URL | Unlisted host denied | Change destination to **Trusted docs host**; offline fixture document loads; no network request |
| 5. Execute command | Denied pending human review | Explicitly approve **echo** or **pwd**; a toy interpreter returns a string, never invoking a system shell |

**Tour all 5 stages** runs one meaningful guarded attempt per stage: successful read, approved email, denied file deletion, allowlisted offline URL, and approved toy command. It shows an audit trail with five entries. Changing stages or execution modes resets pending approval, so it cannot silently authorize later actions.

**Release gate:** `scripts/test_public_demo.mjs` exercises all five paths and the complete tour. `scripts/test_public_demo_browser.py` opens the site in real headless Chromium, clicks each stage, tests approvals, checks results and a mobile-sized viewport, and refuses unexpected external network requests. Neither test establishes real-model prompt-injection attack resistance.

## Current status and verified evidence

- `public-demo/index.html` and `public-demo/sandbox.js` implement five synthetic tool requests, in-memory handlers (fictional read, outbox, file deletion, offline URL fixture), one-use email authorization and denial, local audit log, reset button, three-step walkthrough, copyable Python example, and GitHub feedback issue draft.
- `scripts/verify_public_demo.py` checks expected sections, safety language, exactly one locally bundled JavaScript file, missing anchors, syntax and secret placeholders.
- `scripts/test_public_demo.mjs` simulates UI actions in a local DOM stub and asserts denied approval, explicitly allowed one-time approval, approval reset, unguarded in-memory handlers, file effects, sandbox reset, complete guided walkthrough and GitHub issue draft URL.
- Verified GitHub Actions build: [showcase workflow #42359471308](https://github.com/chirayukapoor5/agentshield/actions/runs/42359471308) — static/JavaScript checks and UI smoke tests passed; deploy job skipped on the PR event.
- Archive of the passing static build: [preview artifact](https://github.com/chirayukapoor5/agentshield/actions/runs/42359471308/artifacts/13569255940).
- Initial **push** deployment attempt failed before Pages was configured. The issue was resolved after selecting **GitHub Actions** in repository Pages settings and replacing the incorrect root-level Next.js workflow with the standalone static showcase publisher on `main`.
- Public developer feedback thread: [GitHub issue #2](https://github.com/chirayukapoor5/agentshield/issues/2). At creation it had **0 external responses**.

## Publishing and troubleshooting

GitHub Pages is already enabled with **Source: GitHub Actions**. The release deployment workflow is [`.github/workflows/nextjs.yml` on `main`](https://github.com/chirayukapoor5/agentshield/blob/main/.github/workflows/nextjs.yml); despite its historical filename, it publishes the verified static `public-demo/` folder from the research branch.

If the page needs refreshing, trigger [Deploy AgentShield showcase to Pages](https://github.com/chirayukapoor5/agentshield/actions/workflows/nextjs.yml) on `main` (or update the main workflow) and verify build + deploy + live HTML/JS checks. Research-branch workflow `verify-agent-shield-showcase` only validates and archives previews, so a green PR job is not a Pages deployment.

If you still see the older scripted page, use Ctrl+Shift+R for a full refresh and check that **Email approval callback** and **Simulated outbox** appear.

### Post-publication smoke checklist

- Visit https://chirayukapoor5.github.io/agentshield/ in a private browser. Confirm the approval dropdown and in-memory outbox count are visible.
- With **Send an email**, **With AgentShield** and the default **Not configured — deny**, click **Execute sandbox tool**. Expect `denied`, `approval_not_configured`, `handler_executed:false` and outbox count **0**.
- Change the email approval dropdown to **Ask reviewer → approve one sandbox email**, click Execute. Expect `allowed`, `approved`, `handler_executed:true`, `delivered:false` and outbox count **1**. The approval dropdown automatically resets to `none`.
- Click Execute once more without re-approving. Expect denial and an unchanged outbox count.
- Switch **Without AgentShield** and execute the email handler. Expect `outside_policy_boundary` with the fictional handler executed and outbox count **2**. No actual email is sent.
- Choose **Read a document** to see a read-only fixture handler execute. **Delete a file** is denied with guard and only affects sandbox memory when unguarded; neither path touches device files.
- Reset the sandbox. Confirm outbox **0**, sample file **Present** and empty audit. Run the guided walkthrough through its three steps.
- Submit non-sensitive example text through the feedback form, verify that a **GitHub issue draft** opens, but do not post a fake issue just to test.

**Verified deployment:** [#42363097365](https://github.com/chirayukapoor5/agentshield/actions/runs/42363097365), deployed page and `sandbox.js` both returned HTTP 200 at 2026-11-07 10:14 UTC. A standalone external browser interaction test remains unverified due to restricted browser networking in this environment.

### 60-second demonstration

**0–10 sec:** “AgentShield puts an authorization check between an agent tool request and the application's handler.”

**10–25 sec:** Choose **Send an email**; with the guard active and no approval, run it. “The request is denied and the outbox stays at zero.”

**25–40 sec:** Choose **Approve one sandbox email** and run. “Now the guard authorizes this *single* call. A fictional email appears in the in-memory outbox; the authorization resets. No real mail is delivered.”

**40–50 sec:** Run again to demonstrate denial, then switch to **Without AgentShield** and show that the unguarded fictional handler executes without the policy check.

**50–60 sec:** Show the complete Python SDK callback example and ask developers for their framework, approval needs and trial interest.

Do not describe this as a real model, actual network/email transmission, AgentDojo attack-success rate, or production security guarantee.

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
