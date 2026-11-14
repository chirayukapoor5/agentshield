from pathlib import Path
import runpy

def test_end_to_end_monitoring_demo(tmp_path):
    module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "examples" / "monitoring_demo.py"))
    result = module["run_demo"](tmp_path)
    assert result["events"] == 5
    assert result["incidents"] == 1
    assert result["denied_handler_executed"] is False
    html = (tmp_path / "incident-dashboard.html").read_text()
    assert "delete_fixture" in html
    assert "No tool arguments recorded" in html
    import json
    report = json.loads((tmp_path / "audit-report.json").read_text())
    assert report["summary"]["denied"] == 4
    assert "arguments" not in (tmp_path / "audit-report.json").read_text()
    assert (tmp_path / "incidents.sqlite").exists()
