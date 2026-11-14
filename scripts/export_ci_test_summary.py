#!/usr/bin/env python3
"""Convert bounded JUnit XML into a minimal, redacted CI summary (stdlib only)."""
import argparse
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_XML_BYTES = 10 * 1024 * 1024
MAX_TESTS = 3000


def fail(message):
    raise ValueError(message)


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def export_summary(data, run_id, python_version, fixture=False):
    if len(data) > MAX_XML_BYTES:
        fail("JUnit XML exceeds size limit")
    try:
        xml_text = data.decode("utf-8", "strict")
    except UnicodeDecodeError:
        fail("JUnit XML must be UTF-8")
    if "\x00" in xml_text:
        fail("JUnit XML must be UTF-8")
    if re.search(r"<!\s*(DOCTYPE|ENTITY)\b", xml_text, re.I):
        fail("DTD and entities are not allowed")
    try:
        root = ET.fromstring(xml_text)
    except (ET.ParseError, ValueError):
        fail("invalid JUnit XML")
    root_tag = _local(root.tag)
    if root_tag not in ("testsuite", "testsuites"):
        fail("invalid JUnit document root")
    if root_tag == "testsuites" and any(_local(child.tag) != "testsuite" for child in root):
        fail("invalid JUnit suite structure")
    suites = [root] if root_tag == "testsuite" else list(root)
    for suite in suites:
        # Validate direct parent/child relationships so stray failure nodes or
        # testcases hidden under properties cannot produce a success summary.
        for child in suite:
            tag = _local(child.tag)
            if tag == "properties":
                if any(_local(prop.tag) != "property" or len(prop) for prop in child):
                    fail("invalid JUnit test structure")
            elif tag == "testcase":
                states = 0
                for detail in child:
                    detail_tag = _local(detail.tag)
                    if detail_tag not in ("failure", "error", "skipped", "system-out", "system-err") or len(detail):
                        fail("invalid JUnit test structure")
                    if detail_tag in ("failure", "error", "skipped"):
                        states += 1
                if states > 1:
                    fail("invalid JUnit test structure")
            elif tag in ("system-out", "system-err"):
                if len(child):
                    fail("invalid JUnit test structure")
            else:
                fail("invalid JUnit test structure")
    cases = [node for node in root.iter() if _local(node.tag) == "testcase"]
    if len(cases) > MAX_TESTS:
        fail("JUnit test count exceeds limit")
    passed = failed = skipped = errors = 0
    failed_ids = []
    elapsed = 0.0
    for case in cases:
        try:
            duration = float(case.attrib.get("time", "0"))
        except (ValueError, OverflowError):
            fail("invalid JUnit duration")
        if not math.isfinite(duration) or duration < 0:
            fail("invalid JUnit duration")
        elapsed += duration
        if not math.isfinite(elapsed) or elapsed > 7 * 24 * 3600:
            fail("JUnit duration exceeds limit")
        children = {_local(child.tag) for child in case}
        if "error" in children:
            errors += 1
            identity = (case.attrib.get("classname", "") + "::" + case.attrib.get("name", "")).encode("utf-8", "replace")
            failed_ids.append(hashlib.sha256(identity).hexdigest())
        elif "failure" in children:
            failed += 1
            # Hash only the test's stable location. Never copy XML names/parameters.
            identity = (case.attrib.get("classname", "") + "::" + case.attrib.get("name", "")).encode("utf-8", "replace")
            failed_ids.append(hashlib.sha256(identity).hexdigest())
        elif "skipped" in children:
            skipped += 1
        else:
            passed += 1
    if len(set(failed_ids)) != len(failed_ids):
        fail("duplicate failed test identifiers")
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
        fail("run ID must be a positive integer")
    if python_version not in ("3.10", "3.12"):
        fail("Python version must be 3.10 or 3.12")
    return {
        "schema_version": 1, "run_id": run_id, "python_version": python_version,
        "passed": passed, "failed": failed, "skipped": skipped, "errors": errors,
        "total": len(cases), "duration_seconds": elapsed, "failed_tests": failed_ids,
        "is_fixture": bool(fixture),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--python-version", required=True, choices=("3.10", "3.12"))
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as stream:
            xml = stream.read(MAX_XML_BYTES + 1)
        report = export_summary(xml, args.run_id, args.python_version, args.fixture)
        output = json.dumps(report, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
        args.output.write_bytes(output)
    except OSError:
        # OS errors can include local paths; keep CLI diagnostics path-free.
        print("export failed: input/output file error", file=sys.stderr)
        return 2
    except ValueError as exc:
        print("export failed: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
