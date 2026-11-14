import pytest
from agentshield_guard.anomaly import (
    OfflineAnomalyDetector, WindowFeatures, extract_window,
)

def test_extract_window_metrics():
    result = extract_window([
        {"tool": "read", "reason": "allowlisted", "allowed": True},
        {"tool": "delete", "reason": "tool_not_allowlisted", "allowed": False},
        {"tool": "send", "reason": "approval_denied", "allowed": False},
    ])
    assert result == WindowFeatures(3, 2 / 3, 1 / 3, 1 / 3, 3)

def test_window_rejects_bad_or_unbounded_input():
    with pytest.raises(ValueError):
        extract_window([])
    with pytest.raises(ValueError):
        extract_window([{"allowed": "False", "tool": "x", "reason": "x"}])
    with pytest.raises(ValueError):
        extract_window([{"allowed": True, "tool": "x", "reason": "x"}] * 3, max_events=2)

def test_requires_training_and_sufficient_baseline():
    detector = OfflineAnomalyDetector()
    with pytest.raises(RuntimeError):
        detector.score(WindowFeatures(1, 0, 0, 0, 1))
    with pytest.raises(ValueError):
        detector.fit([WindowFeatures(1, 0, 0, 0, 1)] * 9)

def test_rejects_invalid_contamination():
    for value in (0, -1, 0.51, float("nan"), True):
        with pytest.raises(ValueError):
            OfflineAnomalyDetector(contamination=value)

def test_reproducible_scoring_when_sklearn_installed():
    pytest.importorskip("sklearn")
    baseline = [WindowFeatures(10 + i, i / 100, 0, 0, 1 + i % 3) for i in range(20)]
    test = WindowFeatures(1000, 0.95, 0.8, 0.7, 20)
    first = OfflineAnomalyDetector().fit(baseline).score(test)
    second = OfflineAnomalyDetector().fit(baseline).score(test)
    assert first == second
    assert first["model"] == "isolation_forest"
    assert isinstance(first["anomaly"], bool)
    assert first["interpretation"] == "statistical_outlier_not_confirmed_attack"
