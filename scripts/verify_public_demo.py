"""Static-showcase release gate: no backend, secrets, or live agent tools.

Run: python scripts/verify_public_demo.py
Optionally pass node to syntax-check the browser script in addition to HTML checks.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path

EXPECTED = {"demo", "walkthrough", "integration", "feedback", "evidence"}
PROHIBITED = ("GROQ_API_KEY", "OPENAI_API_KEY", "password123", "eval(", "fetch(")


class Inspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.script_sources: list[str] = []
        self.form_actions: list[str] = []
        self.has_description = False
        self.has_title = False
        self.scripts: list[str] = []
        self._in_script = False

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if "id" in data:
            if data["id"] in self.ids:
                raise ValueError(f"duplicate HTML id: {data['id']}")
            self.ids.add(data["id"])
        if tag == "a" and "href" in data:
            self.links.append(data["href"])
        if tag == "script":
            if data.get("src"):
                self.script_sources.append(data["src"])
            else:
                self._in_script = True
        if tag == "form":
            self.form_actions.append(data.get("action", ""))
        if tag == "title":
            self.has_title = True
        if tag == "meta" and data.get("name") == "description":
            self.has_description = True

    def handle_data(self, data):
        if self._in_script:
            self.scripts.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = False


def verify(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    inspector = Inspector()
    inspector.feed(text)
    missing = EXPECTED - inspector.ids
    if missing:
        raise ValueError(f"missing landing sections: {sorted(missing)}")
    if not inspector.has_title or not inspector.has_description:
        raise ValueError("missing SEO title or description")
    if inspector.script_sources != ["sandbox.js"]:
        raise ValueError("only the bundled local sandbox.js is allowed")
    if any(action for action in inspector.form_actions):
        raise ValueError("feedback must not submit data to an undeployed backend")
    for link in inspector.links:
        if link.startswith("#") and link[1:] not in inspector.ids and link != "#top":
            raise ValueError(f"broken section link: {link}")
        if link.lower().startswith("javascript:"):
            raise ValueError("javascript links are forbidden")
    bundled_js = (path.parent / "sandbox.js").read_text(encoding="utf-8")
    if any(secret in text or secret in bundled_js for secret in PROHIBITED):
        raise ValueError("potential secret or dangerous runtime expression")
    for required in ("synthetic", "not a", "github.com/chirayukapoor5/agentshield/issues/new",
                     "privacy", "aria-live", "approval-panel", "outbox-count", "sandbox-approval-v2"):
        if required.lower() not in text.lower():
            raise ValueError(f"missing product/demo transparency signal: {required}")
    inline_js = bundled_js
    if not inline_js.strip() or "handler_executed:executed" not in bundled_js:
        raise ValueError("missing executable sandbox JavaScript")
    if shutil.which("node"):
        with tempfile.TemporaryDirectory() as tempdir:
            js_path = Path(tempdir) / "demo.js"
            js_path.write_text(inline_js, encoding="utf-8")
            subprocess.run(["node", "--check", str(js_path)], check=True,
                           timeout=15, capture_output=True)
    return {
        "check": "static_public_demo",
        "result": "passed",
        "sections": sorted(EXPECTED),
        "no_remote_runtime_scripts": True,
        "browser_sandbox_handlers": True,
        "one_time_approval_control": True,
        "no_live_backend": True,
        "feedback_uses_GitHub_issue_redirect": True,
        "node_syntax_checked": bool(shutil.which("node")),
        "not_a_real_model_security_test": True,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file", type=Path, default=Path("public-demo/index.html"))
    args = p.parse_args()
    import json
    print(json.dumps(verify(args.file), indent=2))


if __name__ == "__main__":
    main()
