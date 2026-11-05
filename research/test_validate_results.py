"""Zero-dependency regression tests for the research results validator."""
import json
import tempfile
import unittest
from pathlib import Path

from research.validate_results import summarize, validate, wilson


def trial(**overrides):
    record = {
        "trial_id": "one", "scenario_id": "scenario-1", "split": "dev",
        "condition": "C1", "language": "en", "script": "Latn",
        "code_mixed": False, "defense_id": "baseline", "model_id": "mock",
        "seed": 1, "attacker_queries": 0, "outcome": "scored",
        "success": False, "artifact_ref": "traces/one.json",
    }
    record.update(overrides)
    return record


class ValidatorTests(unittest.TestCase):
    def test_valid_trial(self):
        self.assertEqual(validate(trial(), 1)["trial_id"], "one")

    def test_no_success_on_timeout(self):
        with self.assertRaisesRegex(ValueError, "null success"):
            validate(trial(outcome="timeout"), 1)

    def test_boolean_not_accepted_as_seed(self):
        with self.assertRaisesRegex(ValueError, "seed"):
            validate(trial(seed=True), 1)

    def test_english_adaptive_constraint(self):
        with self.assertRaisesRegex(ValueError, "C4"):
            validate(trial(condition="C4", language="es"), 1)

    def test_static_no_search(self):
        with self.assertRaisesRegex(ValueError, "oracle"):
            validate(trial(attacker_queries=1), 1)

    def test_reject_parent_traversal(self):
        with self.assertRaisesRegex(ValueError, "artifact_ref"):
            validate(trial(artifact_ref="../secrets.txt"), 1)

    def test_duplicate_id_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            data = json.dumps(trial()) + "\n" + json.dumps(trial()) + "\n"
            path.write_text(data, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                summarize(path)

    def test_non_scored_remain_in_total(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            records = [
                trial(trial_id="one", success=True),
                trial(trial_id="two", outcome="timeout", success=None),
            ]
            path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
            row = summarize(path)["groups"][0]
            self.assertEqual((row["total"], row["scored"], row["successes"]), (2, 1, 1))
            self.assertEqual(row["outcomes"]["timeout"], 1)

    def test_wilson_empty(self):
        self.assertIsNone(wilson(0, 0))

    def test_wilson_bounds(self):
        self.assertEqual(wilson(0, 1)[0], 0.0)
        self.assertEqual(wilson(1, 1)[1], 1.0)


if __name__ == "__main__":
    unittest.main()
