# AgentShield Public Research Lab — Demo Guide

**Route:** `/lab` inside the existing Next.js frontend.  
**Status:** prototype; responsive static demonstration, not a live agent-security verdict.

## Run the website locally
```bash
cd frontend
npm ci
npm run dev
```
Visit `http://localhost:3000/lab`. No account, Groq API key, database, or backend is required for this route.

## What viewers can show
1. Open the interactive simulation, choose **Send an email without approval**, and press **Run simulation**. The terminal will replay an `approval_not_configured` denial.
2. Switch to **Read a document**, then **Fetch an approved HTTPS URL**, to demonstrate that explicitly allowed calls can proceed.
3. Choose **Lookalike hostname** or **Invoke an unregistered tool** to show the fail-closed policy boundary.
4. Open the linked GitHub Actions checks for the 13 passing SDK tests, 20 successful Groq chat-completion calls, and the eight-case toy policy demonstration.
5. For a social video, use an ordinary screen recorder in 16:9 landscape orientation; keep the words **SYNTHETIC · OFFLINE** visible and show the evidence links.

This is a browser replay of the deterministic examples in `sdk/examples/demo_stats.py`. It does not issue real tool calls, access the Internet, run an LLM, or execute untrusted code.

## Hosting
The optional `publish-demo.yml` workflow builds an export using the base path `/agentshield` and attempts deployment to GitHub Pages. Deployment requires the repository's Pages configuration to allow GitHub Actions; **do not claim a public URL until the deployment job succeeds and the site is reachable**.

On normal development builds, the new route remains `/lab`; no static-export settings are active.

## Evidence boundaries
- **13 tests:** SDK test assertions, not adversarial attack successes.
- **8/8 decisions:** scripted simulated scenarios with expected outcomes, not statistical ASR.
- **20/20 API success:** basic Groq chat-completion requests and zero HTTP 429 responses in one smoke test, not tool-calling or security evaluation.
- **Unmeasured:** AgentDojo C1–C4 ASR, utility, learned-detector miss rates, end-to-end tool-using attack resistance and real-world safety.

Do not post claims like “100% protection,” “all prompt injections blocked,” or “production-ready.” Cite the run links on the page alongside the limitations.
