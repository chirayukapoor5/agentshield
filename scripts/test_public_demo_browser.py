"""Real Chromium UI acceptance test for every AgentShield public showcase stage.

Prerequisites: pip install playwright==1.57.0 && python -m playwright install chromium
Run: python scripts/test_public_demo_browser.py
Uses only file:// assets. No LLM, external network requests or real tools.
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = (ROOT / "public-demo" / "index.html").as_uri()
SHOT = ROOT / "data" / "ui-acceptance"


def trace(page) -> dict:
    return json.loads(page.locator("#trace").inner_text())


def main() -> None:
    SHOT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        issues = []
        page = browser.new_page(viewport={"width": 1344, "height": 900})
        page.on("pageerror", lambda e: issues.append(str(e)))
        external = []
        page.on("request", lambda r: external.append(r.url)
                if r.url.startswith(("http://", "https://")) else None)
        page.goto(SITE)
        page.wait_for_function("document.querySelectorAll('#scenarios button').length===5")
        assert page.locator("#stage-progress").inner_text() == "Stage 1 of 5"

        # Read.
        page.click("#run")
        assert trace(page)["decision"] == "allowed"
        assert trace(page)["handler_executed"] is True
        assert page.locator("#read-count").inner_text() == "1"
        assert "Synthetic research note" in page.locator("#sandbox-output").inner_text()

        # Email: deny, approve once, then deny again.
        page.locator("#scenarios button").nth(1).click()
        page.click("#run")
        assert trace(page)["reason"] == "approval_required"
        assert page.locator("#outbox-count").inner_text() == "0"
        page.select_option("#approval", "approve")
        page.click("#run")
        assert trace(page)["reason"] == "approved_one_time"
        assert trace(page)["sandbox_result"]["delivered"] is False
        assert page.locator("#outbox-count").inner_text() == "1"
        page.click("#run")
        assert trace(page)["decision"] == "denied"
        assert page.locator("#outbox-count").inner_text() == "1"

        # Deletion: denied then explicitly allowed (fictional file only).
        page.locator("#scenarios button").nth(2).click()
        page.click("#run")
        assert trace(page)["decision"] == "denied"
        assert page.locator("#file-status").inner_text() == "Present"
        page.select_option("#approval", "approve")
        page.click("#run")
        assert trace(page)["sandbox_result"]["real_file_touched"] is False
        assert page.locator("#file-status").inner_text() == "Deleted (sandbox)"

        # Fetch: blocked destination, then a trusted exact HTTPS host.
        page.locator("#scenarios button").nth(3).click()
        page.click("#run")
        assert trace(page)["reason"] == "destination_not_allowlisted"
        page.select_option("#destination", "https://docs.agentshield.test/guide")
        page.click("#run")
        assert trace(page)["decision"] == "allowed"
        assert trace(page)["sandbox_result"]["network_requested"] is False
        assert page.locator("#fetch-count").inner_text() == "1"

        # Shell: blocked, then toy interpreter approval.
        page.locator("#scenarios button").nth(4).click()
        page.click("#run")
        assert trace(page)["reason"] == "approval_required"
        page.select_option("#approval", "approve")
        page.select_option("#command-choice", "pwd")
        page.click("#run")
        assert trace(page)["decision"] == "allowed"
        assert trace(page)["sandbox_result"]["real_shell_started"] is False
        assert trace(page)["sandbox_result"]["stdout"] == "/synthetic/agent-workspace"
        assert page.locator("#command-count").inner_text() == "1"

        # All steps also have a functional unguarded synthetic handler.
        page.click("#without")
        page.click("#run")
        assert trace(page)["decision"] == "outside_policy_boundary"
        assert trace(page)["handler_executed"] is True

        # Reset and 5-stage walkthrough.
        page.click("#reset-sandbox")
        assert page.locator("#outbox-count").inner_text() == "0"
        assert page.locator("#file-status").inner_text() == "Present"
        # Reduce only UI tour timers to avoid an 8s CI wait.
        page.evaluate("""() => {
          const original = window.setTimeout.bind(window);
          window.setTimeout = (f, t, ...a) => original(f, Math.min(t, 80), ...a);
        }""")
        page.click("#guided")
        page.wait_for_function("""() =>
          document.querySelector('#stage-progress').textContent === 'Stage 5 of 5'
          && JSON.parse(document.querySelector('#trace').textContent).decision === 'allowed'
        """, timeout=10000)
        assert page.locator("#outbox-count").inner_text() == "1"
        assert page.locator("#read-count").inner_text() == "1"
        assert page.locator("#file-status").inner_text() == "Present"
        assert page.locator("#fetch-count").inner_text() == "1"
        assert page.locator("#command-count").inner_text() == "1"
        assert len(json.loads(page.locator("#audit").inner_text())) == 5
        page.screenshot(path=str(SHOT / "desktop-five-stages.png"), full_page=True)

        # Feedback opens a draft, not an unconsented post or hidden backend.
        page.evaluate("window.open = url => { window.__draft = url; return null; }")
        page.select_option("#framework", "Custom Python agent")
        page.select_option("#interest", "Yes, this month")
        page.fill("#problem", "Need human approval for file changes in my sandbox")
        page.locator("#feedback-form button[type=submit]").click()
        draft = page.evaluate("window.__draft")
        assert draft.startswith("https://github.com/chirayukapoor5/agentshield/issues/new?")
        assert "file+changes" in draft or "file%20changes" in draft
        assert not external, "unexpected external network request from sandbox: " + repr(external)
        assert not issues, "page errors: " + repr(issues)

        # Mobile smoke for the same real HTML+JS entrypoint.
        mobile = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
        mobile.on("pageerror", lambda e: issues.append(str(e)))
        mobile.goto(SITE)
        mobile.locator("#scenarios button").nth(3).click()
        mobile.select_option("#destination", "https://docs.agentshield.test/policy")
        mobile.click("#run")
        assert trace(mobile)["decision"] == "allowed"
        overflow = mobile.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert overflow <= 1, "horizontal mobile overflow: " + str(overflow)
        mobile.screenshot(path=str(SHOT / "mobile-url-stage.png"), full_page=True)
        assert not issues, "browser JS errors: " + repr(issues)
        browser.close()
    print("PASS: Chromium desktop/mobile, 5 tools, denied/approved execution, exact host, synthetic command, guided tour, feedback draft, zero external requests.")


if __name__ == "__main__":
    main()
