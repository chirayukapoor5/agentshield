# Verified Groq connectivity preflight — November 5, 2026

**Scope:** provider authentication and basic chat-completion connectivity ONLY. Not a prompt-injection or tool-calling benchmark.

- Workflow: [Groq credential preflight run #42050250859](https://github.com/chirayukapoor5/agentshield/actions/runs/42050250859)
- Redacted metadata: [GitHub Actions artifact](https://github.com/chirayukapoor5/agentshield/actions/runs/42050250859/artifacts/13426701036) (short retention)
- Provider: GroqCloud, OpenAI-compatible endpoint
- Model: `openai/gpt-oss-120b`
- Chat-completion attempts: **20**
- Successful responses (HTTP 200): **20**
- HTTP 429 responses: **0**
- Chat completion success in this controlled smoke test: **20 / 20**
- Date/time: 2026-11-05T15:00:56Z, as reported by the run
- Credential: repository secret `GROQ_API_KEY`; key value intentionally not logged or committed

The account's reported model catalog included `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`, `meta-llama/llama-prompt-guard-2-22m` and `meta-llama/llama-prompt-guard-2-86m` among other IDs. Model listing **does not prove** model-specific tool calling or classifier semantics. No exact free quota, sustainable RPM or paid rate was established from this sample.

## Interpretation
A 20/20 connectivity result does **not** imply AgentDojo benchmark success, safety, jailbreak resistance, free-tier sustainability, or statistical robustness. Real adaptive experiments remain not run.

## Operational change
The credential preflight workflow was changed to **manual-only** (`workflow_dispatch`) after the successful run, to prevent subsequent source changes from triggering repeated real calls. The app-level global budget ledger is not shared across different GitHub Actions job instances; do not schedule independent experiments without an external shared cap.
