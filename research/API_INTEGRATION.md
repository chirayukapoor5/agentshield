# Integration gates / verified API facts
Verified 2026-11-05 against upstream docs and source:
- AgentDojo PyPI currently declares package version **0.1.35**; the package says its API is subject to change.
- Upstream `agent_pipeline/agent_pipeline.py` defines `DEFENSES = ["tool_filter", "transformers_pi_detector", "spotlighting_with_delimiting", "repeat_user_prompt"]`.
- `PipelineConfig.from_config` accepts custom `BasePipelineElement` objects for LLMs, not only string model enum values.
- `tool_filter` explicitly requires `OpenAILLM`. A generic OpenAI-compatible chat client is **not** guaranteed to integrate without adapting the tool-filter class, and its extra calls must be budgeted.
- Built-in transformer detector defaults to `protectai/deberta-v3-base-prompt-injection-v2`; this is not Llama Prompt Guard 2.
- Upstream docs use `python -m agentdojo.scripts.benchmark -s workspace -ut user_task_0 --model ... --defense tool_filter --attack tool_knowledge`.
Sources: https://github.com/ethz-spylab/agentdojo/blob/main/src/agentdojo/agent_pipeline/agent_pipeline.py ; https://agentdojo.spylab.ai/api/agent_pipeline/defenses/ ; https://pypi.org/project/agentdojo/

## Remaining implementation blockers
The container cannot reach PyPI/GitHub and AgentDojo is **not** installed. Before a real experiment, install pinned AgentDojo locally, verify runtime signatures and inspect the user/injection task checker interfaces. Implement tested official checker integration; replace `evaluate_official`'s deliberate hard failure. Verify classifier licenses and explicit model-language coverage from model cards, then freeze exact detector revision. Nothing in this scaffold should be described as an AgentDojo benchmark execution.
