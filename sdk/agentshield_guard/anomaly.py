"""Optional, offline anomaly scoring of aggregate AgentShield security events.

Train only on explicitly supplied baseline windows. No model calls or raw prompts.
Scores are descriptive anomaly flags, not attack verdicts.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Iterable

@dataclass(frozen=True)
class WindowFeatures:
    total: int
    denial_ratio: float
    unknown_tool_ratio: float
    approval_denial_ratio: float
    distinct_tools: int

def extract_window(events: Iterable[dict], *, max_events: int = 10000) -> WindowFeatures:
    if type(max_events) is not int or not 1 <= max_events <= 100000:
        raise ValueError("invalid max_events")
    total = denied = unknown = approvals = 0
    tools: set[str] = set()
    for event in events:
        total += 1
        if total > max_events:
            raise ValueError("window exceeds event limit")
        if not isinstance(event, dict) or type(event.get("allowed")) is not bool:
            raise ValueError("invalid event")
        tool, reason = event.get("tool"), event.get("reason")
        if not isinstance(tool, str) or not isinstance(reason, str):
            raise ValueError("invalid event metadata")
        tools.add(tool)
        if not event["allowed"]:
            denied += 1
        unknown += reason == "tool_not_allowlisted"
        approvals += reason in {"approval_denied", "approval_not_configured"}
    if total == 0:
        raise ValueError("empty event window")
    return WindowFeatures(total, denied / total, unknown / total,
                          approvals / total, len(tools))

def _vector(features: WindowFeatures) -> list[float]:
    return [float(features.total), features.denial_ratio,
            features.unknown_tool_ratio, features.approval_denial_ratio,
            float(features.distinct_tools)]

class OfflineAnomalyDetector:
    """Optional scikit-learn IsolationForest; deterministic fixed seed.

    Requires: pip install scikit-learn. Do not train on held-out AgentDojo data.
    """
    def __init__(self, *, contamination: float = 0.1):
        if type(contamination) not in (float, int) or not isfinite(contamination) or not 0 < contamination <= 0.5:
            raise ValueError("invalid contamination")
        self.contamination = contamination
        self._model = None

    def fit(self, baseline: Iterable[WindowFeatures]):
        from sklearn.ensemble import IsolationForest
        samples = list(baseline)
        if len(samples) < 10 or any(not isinstance(x, WindowFeatures) for x in samples):
            raise ValueError("at least 10 valid baseline windows required")
        model = IsolationForest(n_estimators=100, contamination=self.contamination,
                                random_state=42, n_jobs=1)
        model.fit([_vector(s) for s in samples])
        self._model = model
        return self

    def score(self, features: WindowFeatures) -> dict:
        if self._model is None:
            raise RuntimeError("detector is not fitted")
        if not isinstance(features, WindowFeatures):
            raise TypeError("features required")
        vector = [_vector(features)]
        score = float(self._model.decision_function(vector)[0])
        return {"anomaly": bool(self._model.predict(vector)[0] == -1),
                "decision_score": score, "model": "isolation_forest",
                "interpretation": "statistical_outlier_not_confirmed_attack"}
