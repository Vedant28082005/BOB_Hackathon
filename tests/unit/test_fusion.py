"""Unit tests for the fusion engine — weights, thresholds, hard-fail overrides."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from engines.fusion import fuse

WEIGHTS = {
    "document": 0.30, "biometric": 0.25, "device": 0.20,
    "behavioural": 0.10, "identity_graph": 0.15,
}
THRESHOLDS = {"approve": 75.0, "step_up": 55.0, "manual_review": 35.0}


def _pipeline(doc=90, bio=90, dev=90, beh=90, graph=90, extra_flags=None):
    p = {
        "document":       {"score": doc,   "flags": [], "signals": {}},
        "biometric":      {"score": bio,   "flags": [], "signals": {}},
        "device":         {"score": dev,   "flags": [], "signals": {}},
        "behavioural":    {"score": beh,   "flags": [], "signals": {}},
        "identity_graph": {"score": graph, "flags": [], "signals": {}},
    }
    if extra_flags:
        for stage, flags in extra_flags.items():
            p[stage]["flags"] = flags
    return p


class TestDecisionThresholds:
    def test_approve_at_high_score(self):
        r = fuse(_pipeline(), WEIGHTS, THRESHOLDS)
        assert r["decision"] == "APPROVE"
        assert r["trust_score"] >= 75.0

    def test_step_up_at_medium_score(self):
        p = _pipeline(doc=60, bio=55, dev=60, beh=60, graph=60)
        r = fuse(p, WEIGHTS, THRESHOLDS)
        assert r["decision"] in ("STEP_UP", "MANUAL_REVIEW")

    def test_reject_at_low_score(self):
        p = _pipeline(doc=20, bio=20, dev=20, beh=20, graph=20)
        r = fuse(p, WEIGHTS, THRESHOLDS)
        assert r["decision"] == "REJECT"

    def test_score_is_weighted_sum(self):
        p = _pipeline(doc=100, bio=100, dev=100, beh=100, graph=100)
        r = fuse(p, WEIGHTS, THRESHOLDS)
        assert abs(r["trust_score"] - 100.0) < 1.0


class TestHardFailOverrides:
    def test_deepfake_forces_reject(self):
        p = _pipeline(bio=95, extra_flags={"biometric": ["BIO_DEEPFAKE"]})
        r = fuse(p, WEIGHTS, THRESHOLDS)
        assert r["decision"] == "REJECT"

    def test_liveness_fail_forces_reject(self):
        p = _pipeline(bio=80, extra_flags={"biometric": ["LIVENESS_FAIL"]})
        r = fuse(p, WEIGHTS, THRESHOLDS)
        assert r["decision"] == "REJECT"

    def test_duplicate_forces_reject(self):
        p = _pipeline(graph=90, extra_flags={"identity_graph": ["GRAPH_DUPLICATE"]})
        r = fuse(p, WEIGHTS, THRESHOLDS)
        assert r["decision"] == "REJECT"

    def test_tampered_doc_forces_manual_review(self):
        # Score alone would approve, but tampered doc overrides
        p = _pipeline(doc=90, extra_flags={"document": ["DOC_TAMPERED"]})
        r = fuse(p, WEIGHTS, THRESHOLDS)
        assert r["decision"] == "MANUAL_REVIEW"

    def test_ring_member_forces_manual_review(self):
        p = _pipeline(graph=90, extra_flags={"identity_graph": ["GRAPH_RING_MEMBER"]})
        r = fuse(p, WEIGHTS, THRESHOLDS)
        assert r["decision"] == "MANUAL_REVIEW"

    def test_reject_takes_priority_over_manual(self):
        # Both DEEPFAKE and RING_MEMBER → REJECT wins
        p = _pipeline(extra_flags={
            "biometric": ["BIO_DEEPFAKE"],
            "identity_graph": ["GRAPH_RING_MEMBER"],
        })
        r = fuse(p, WEIGHTS, THRESHOLDS)
        assert r["decision"] == "REJECT"


class TestReasonCodes:
    def test_reason_codes_sorted_by_severity(self):
        p = _pipeline(extra_flags={
            "biometric": ["BIO_DEEPFAKE"],
            "device": ["TZ_IP_MISMATCH"],
            "identity_graph": ["GRAPH_RING_MEMBER"],
        })
        r = fuse(p, WEIGHTS, THRESHOLDS)
        sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        codes = r["reason_codes"]
        for i in range(len(codes) - 1):
            assert sev_order[codes[i]["severity"]] <= sev_order[codes[i+1]["severity"]]

    def test_no_reason_codes_for_clean_assessment(self):
        r = fuse(_pipeline(), WEIGHTS, THRESHOLDS)
        # No flags → no non-INFO codes (or very few)
        non_info = [c for c in r["reason_codes"] if c["severity"] != "INFO"]
        assert len(non_info) == 0


class TestWeightConfiguration:
    def test_custom_weights_affect_score(self):
        heavy_doc_weights = {**WEIGHTS, "document": 0.90, "biometric": 0.025,
                              "device": 0.025, "behavioural": 0.025, "identity_graph": 0.025}
        p = _pipeline(doc=10, bio=100, dev=100, beh=100, graph=100)
        r = fuse(p, heavy_doc_weights, THRESHOLDS)
        # Document is terrible, heavily weighted → low score
        assert r["trust_score"] < 50.0

    def test_custom_thresholds(self):
        strict = {"approve": 90.0, "step_up": 70.0, "manual_review": 50.0}
        p = _pipeline(doc=80, bio=80, dev=80, beh=80, graph=80)
        r = fuse(p, WEIGHTS, strict)
        # ~80 score would APPROVE with default thresholds but not strict
        assert r["decision"] in ("STEP_UP", "MANUAL_REVIEW")
