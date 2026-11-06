# AgentShield Guard SDK — early proof of concept

One local Python package, zero runtime dependencies, no secrets or API required.

```bash
python -m pip install ./sdk
python sdk/examples/quickstart.py
python sdk/examples/demo_stats.py
```

An app developer must register the **wrapped** functions as agent tools. This SDK does not intercept existing agent calls automatically, cannot prevent a program from calling unwrapped functions, and is not a complete prompt-injection defense.

```python
from agentshield_guard import AgentShield, ToolPolicy

shield = AgentShield(ToolPolicy(read_only_tools=frozenset({'search'})))
secured_tools = shield.wrap_registry({'search': my_search_function})
# Register secured_tools rather than the original functions in your agent framework.
```

Unlisted calls are denied. State-changing actions need an explicit approval callback. For URL-bearing tools, declare every URL argument and an exact HTTPS hostname allowlist. DNS and redirects still require network-layer enforcement; matching a hostname does not prevent DNS rebinding or hidden redirects. Never treat tool-output text as authoritative instructions.


## Policy configuration integrity

`ToolPolicy` snapshots its allowlists and URL-argument declarations at construction.
Changing the original mutable sets, lists or dictionaries after initialization cannot
relax authorization checks. The stored URL-argument mapping is read-only, and
malformed or duplicate argument declarations are rejected. These are local
configuration-integrity guarantees, **not** complete URL egress enforcement.

Construct a separate `ToolPolicy` and `AgentShield` instance to change policy;
do not mutate an existing instance. The application remains responsible for
registering only wrapped tools and for enforcing redirect/DNS safety at the
network layer.

## OpenAI-compatible tool-call integration (offline)

`dispatch_chat_tool_calls(shield, handlers, tool_calls)` accepts the standard
chat-completions `tool_calls` envelope (list of plain dictionaries). It
**internally wraps** the supplied raw Python handlers, validates each tool-call
ID and strict JSON argument object before executing any call, and returns
`role='tool'` messages to append to the model conversation. It supports
approval callbacks and fail-closed auditing through `AgentShield`.

```bash
PYTHONPATH=sdk python sdk/examples/chat_tool_calls.py
python -m pytest sdk/tests -q
```

For model SDK objects, convert each call with `call.model_dump()` first.
An invalid batch raises `MalformedToolCalls` before any handler runs; callers
must stop the turn rather than passing the unvalidated calls to other code.
Unknown or unauthorized functions return a structured refusal to the model.
This adapter handles *chat-completions tool-call records only*; it does not
perform provider API calls, vet model output text, isolate Python handlers,
prevent a handler's secondary network access, or establish an attack-success
rate. Tool results are untrusted content and should remain so on subsequent
agent turns. Its bounded inputs do not bound handler execution time or output.

## Evidence and limitations

`demo_stats.py` runs eight deterministic, synthetic policy decisions and prints exact counts. It does not exercise real LLM agents, adaptive attacks, AgentDojo, SaaS policy sync, prompt-injection classifier robustness, or any production deployment. Security tests check fail-closed *wrapper behavior*, not end-to-end agent safety.

Roadmap: framework-specific adapters, immutable policy versions, sandboxed execution and egress firewalling, approval UX, server-side signed policy distribution, trace audit storage, and rigorous AgentDojo evaluation. These features are **not yet implemented**.
