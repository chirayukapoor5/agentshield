import hashlib
import importlib.util
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from agentshield_mcp_ci.reports import LocalReportStore, ReportError, read_report, validate_report

SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "export_ci_test_summary.py"))
spec = importlib.util.spec_from_file_location("export_ci_test_summary", SCRIPT)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def report(**updates):
    value = {"schema_version": 1, "run_id": 12, "python_version": "3.12", "passed": 1,
             "failed": 1, "skipped": 0, "errors": 0, "total": 2, "duration_seconds": 0.5,
             "failed_tests": ["a" * 64], "is_fixture": False}
    value.update(updates)
    return value


def test_reads_valid_strict_report():
    value = report()
    assert read_report(json.dumps(value).encode()) == value


@pytest.mark.parametrize("updates", [
    {"run_id": True}, {"run_id": 0}, {"python_version": "3.11"}, {"total": 3},
    {"duration_seconds": float("nan")}, {"duration_seconds": -1}, {"failed_tests": ["plain-name"]},
    {"failed_tests": ["a" * 64, "a" * 64]}, {"unexpected": "field"}, {"is_fixture": 0},
])
def test_rejects_invalid_schema(updates):
    with pytest.raises(ReportError):
        validate_report(report(**updates))


def test_rejects_malformed_duplicate_and_oversized_json():
    with pytest.raises(ReportError):
        read_report(b"{")
    with pytest.raises(ReportError):
        read_report(b'{"a":1,"a":2}')
    with pytest.raises(ReportError):
        read_report(b" " * (256 * 1024 + 1))
    with pytest.raises(ReportError):
        read_report(b"[1,2,3]")


def test_store_uses_fixed_names_validates_identity_and_rejects_symlinks(tmp_path):
    p = tmp_path / "run-12-py-3.12.json"
    p.write_text(json.dumps(report()), encoding="utf-8")
    store = LocalReportStore(tmp_path)
    assert store.get_report(12, "3.12")["run_id"] == 12
    assert store.get_report(13, "3.12") is None
    with pytest.raises(ReportError):
        store.get_report(12, "../../secrets")
    p.unlink()
    target = tmp_path / "target.json"
    target.write_text(json.dumps(report()), encoding="utf-8")
    p.symlink_to(target)
    with pytest.raises(ReportError):
        store.get_report(12, "3.12")


def test_store_without_version_prefers_312_then_falls_back(tmp_path):
    (tmp_path / "run-12-py-3.10.json").write_text(json.dumps(report(python_version="3.10")), encoding="utf-8")
    (tmp_path / "run-12-py-3.12.json").write_text(json.dumps(report()), encoding="utf-8")
    store = LocalReportStore(tmp_path)
    assert store.get_report(12)["python_version"] == "3.12"
    (tmp_path / "run-12-py-3.12.json").unlink()
    assert store.get_report(12)["python_version"] == "3.10"


def test_exports_only_redacted_failure_hashes():
    secret = "customer@example.com?token=secret"
    xml = f'<testsuite><testcase classname="suite" name="{secret}" time="0.2"><failure message="password=secret">secret trace</failure></testcase><testcase name="ok" /></testsuite>'.encode()
    result = exporter.export_summary(xml, 5, "3.10")
    assert result["failed_tests"] == [hashlib.sha256(("suite::" + secret).encode()).hexdigest()]
    assert result["failed"] == 1 and result["passed"] == 1 and result["total"] == 2
    serialized = json.dumps(result)
    assert secret not in serialized and "secret trace" not in serialized and "password" not in serialized
    assert result["is_fixture"] is False
    assert exporter.export_summary(xml, 5, "3.10", fixture=True)["is_fixture"] is True


def test_export_counts_and_hashes_errors():
    xml = b'<testsuite><testcase classname="suite" name="broken"><error message="secret"/></testcase></testsuite>'
    result = exporter.export_summary(xml, 9, "3.12")
    assert result["errors"] == 1 and result["failed"] == 0
    assert len(result["failed_tests"]) == 1
    assert read_report(json.dumps(result).encode()) == result


@pytest.mark.parametrize("xml", [b"not xml", b'<!DOCTYPE x [<!ENTITY a "boom">]><testsuite/>', b'<testsuite><testcase time="NaN"/></testsuite>'])
def test_export_rejects_untrusted_or_invalid_xml(xml):
    with pytest.raises(ValueError):
        exporter.export_summary(xml, 1, "3.12")


def test_export_rejects_duplicate_ids_and_zip_payload():
    xml = b'<testsuite><testcase classname="a" name="x"><failure/></testcase><testcase classname="a" name="x"><failure/></testcase></testsuite>'
    with pytest.raises(ValueError):
        exporter.export_summary(xml, 1, "3.12")
    with pytest.raises(ValueError):
        exporter.export_summary(b"PK\x03\x04not json or xml", 1, "3.12")


def test_export_rejects_input_and_case_limits():
    with pytest.raises(ValueError):
        exporter.export_summary(b" " * (exporter.MAX_XML_BYTES + 1), 1, "3.12")
    with pytest.raises(ValueError):
        exporter.export_summary(b"<testsuite>" + b"<testcase/>" * (exporter.MAX_TESTS + 1) + b"</testsuite>", 1, "3.12")


@pytest.mark.parametrize("xml", [
    '<!DOCTYPE testsuite><testsuite/>'.encode("utf-16"),
    b"<root><testcase/></root>", b"<testsuite><unknown/></testsuite>",
    b"<testsuite><testcase time=\"604801\"/></testsuite>",
])
def test_export_rejects_non_utf8_dtd_non_junit_and_excessive_duration(xml):
    with pytest.raises(ValueError):
        exporter.export_summary(xml, 1, "3.12")


@pytest.mark.parametrize("xml", [
    b"<testsuite><failure/></testsuite>",
    b"<testsuite><properties><testcase/></properties></testsuite>",
    b"<testsuite><testcase><failure/><error/></testcase></testsuite>",
    b"<testsuite><testcase><failure><unexpected/></failure></testcase></testsuite>",
])
def test_export_rejects_misplaced_or_ambiguous_test_results(xml):
    with pytest.raises(ValueError, match="invalid JUnit test structure"):
        exporter.export_summary(xml, 1, "3.12")


def test_export_cli_filesystem_errors_do_not_echo_paths(tmp_path, capsys):
    private_path = tmp_path / "private-directory-name" / "secret-input.xml"
    result = exporter.main(["--input", str(private_path), "--output", str(tmp_path / "out.json"),
                           "--run-id", "1", "--python-version", "3.12"])
    captured = capsys.readouterr()
    assert result == 2
    assert "input/output file error" in captured.err
    assert str(private_path) not in captured.err
