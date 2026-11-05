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

## Evidence and limitations

`demo_stats.py` runs eight deterministic, synthetic policy decisions and prints exact counts. It does not exercise real LLM agents, adaptive attacks, AgentDojo, SaaS policy sync, prompt-injection classifier robustness, or any production deployment. Security tests check fail-closed *wrapper behavior*, not end-to-end agent safety.

Roadmap: framework-specific adapters, immutable policy versions, sandboxed execution and egress firewalling, approval UX, server-side signed policy distribution, trace audit storage, and rigorous AgentDojo evaluation. These features are **not yet implemented**.
