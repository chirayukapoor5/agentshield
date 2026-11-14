"""End-to-end five-tool example exercising the REAL AgentShield Python guard.

Run from repository root:
  PYTHONPATH=sdk python sdk/examples/five_stage_guard_demo.py

All data and tool results are fictional. No email, network, OS shell, disk
deletion, or external model calls can occur. The guard is not a sandbox for
arbitrary registered handlers; here the handlers themselves are harmless.
"""
from __future__ import annotations

import json

from agentshield_guard import AgentShield, DeniedToolCall, ToolPolicy


def simulate() -> dict:
    state = {"outbox": [], "file_present": True, "reads": 0,
             "offline_fetches": 0, "toy_commands": 0}
    audit = []
    approved = set()

    def approve_once(tool: str) -> None:
        """Fictional operator authorizes exactly one invocation of a tool."""
        approved.add(tool)

    def review(tool: str, args: dict) -> bool:
        if tool in approved:
            approved.remove(tool)
            return True
        return False

    def read_document(id: str) -> dict:
        state["reads"] += 1
        return {"id": id, "document": "Synthetic research note"}

    def send_email(to: str, body: str) -> dict:
        state["outbox"].append({"to": to, "body": body, "delivered": False})
        return {"outbox_size": len(state["outbox"]), "delivered": False}

    def delete_file(path: str) -> dict:
        deleted = path == "sample.txt" and state["file_present"]
        if deleted:
            state["file_present"] = False
        return {"deleted": deleted, "real_file_touched": False}

    def fetch_url(url: str) -> dict:
        state["offline_fetches"] += 1
        return {"url": url, "offline_fixture": "Synthetic policy documentation",
                "network_requested": False}

    def execute_shell(command: str) -> dict:
        # A toy conditional, not subprocess.run, os.system, eval or an OS shell.
        output = {"echo AgentShield demo": "AgentShield demo",
                  "pwd": "/synthetic/agent-workspace"}.get(command)
        if output is None:
            raise ValueError("unsupported fictional command")
        state["toy_commands"] += 1
        return {"stdout": output, "real_shell_started": False}

    shield = AgentShield(
        ToolPolicy(
            read_only_tools={"read_document", "fetch_url"},
            approval_tools={"send_email", "delete_file", "execute_shell"},
            allowed_hosts={"docs.agentshield.test"},
            url_args={"fetch_url": ("url",)},
        ),
        approve=review,
        audit=lambda d: audit.append({"tool": d.tool, "allowed": d.allowed,
                                      "reason": d.reason}),
    )
    guarded = shield.wrap_registry({
        "read_document": read_document,
        "send_email": send_email,
        "delete_file": delete_file,
        "fetch_url": fetch_url,
        "execute_shell": execute_shell,
    })
    outcomes = []

    def call(label: str, tool: str, **args) -> None:
        try:
            result = guarded[tool](**args)
            outcomes.append({"stage": label, "tool": tool,
                             "decision": "allowed", "result": result})
        except DeniedToolCall as exc:
            # Only policy reasons are recorded; no raw tool arguments or secrets.
            outcomes.append({"stage": label, "tool": tool,
                             "decision": "denied",
                             "reason": str(exc).split(": ", 1)[-1]})

    call("1_read", "read_document", id="sample-1")
    call("2_email_denied", "send_email",
         to="demo@example.org", body="Synthetic demo message")
    approve_once("send_email")
    call("2_email_approved", "send_email",
         to="demo@example.org", body="Synthetic demo message")
    call("2_email_again_denied", "send_email",
         to="demo@example.org", body="Synthetic demo message")
    call("3_delete_denied", "delete_file", path="sample.txt")
    approve_once("delete_file")
    call("3_delete_approved", "delete_file", path="sample.txt")
    call("4_url_denied", "fetch_url", url="https://unlisted.example.test/demo")
    call("4_url_allowed", "fetch_url", url="https://docs.agentshield.test/guide")
    call("5_command_denied", "execute_shell", command="echo AgentShield demo")
    approve_once("execute_shell")
    call("5_command_approved", "execute_shell", command="echo AgentShield demo")

    return {"source": "actual_python_agentshield_guard", "synthetic_only": True,
            "outcomes": outcomes, "state": state, "audit": audit}


if __name__ == "__main__":
    print(json.dumps(simulate(), indent=2, ensure_ascii=False))
