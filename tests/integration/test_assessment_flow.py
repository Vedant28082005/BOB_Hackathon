"""
Integration test — full assessment submission + poll cycle.
Requires a running backend (docker-compose up or uvicorn).
Set TRUSTLAYER_TEST_URL env var (default: http://localhost:8000).
"""
import os
import time
import pytest
import httpx

BASE_URL = os.environ.get("TRUSTLAYER_TEST_URL", "http://localhost:8000")
TEST_TOKEN = None


@pytest.fixture(scope="session")
def auth_token():
    resp = httpx.post(f"{BASE_URL}/v1/auth/token", data={
        "username": "analyst@trustlayer.in",
        "password": "analyst123",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


def _wait_for_result(job_id: str, headers: dict, max_wait: int = 60) -> dict:
    """Poll until SUCCESS or FAILURE."""
    for _ in range(max_wait):
        r = httpx.get(f"{BASE_URL}/v1/assessments/{job_id}/result", headers=headers)
        data = r.json()
        if data.get("status") == "SUCCESS":
            return data
        if data.get("status") == "FAILURE":
            pytest.fail(f"Pipeline failed: {data}")
        time.sleep(1)
    pytest.fail(f"Timed out waiting for job {job_id}")


@pytest.mark.integration
class TestAssessmentFlow:
    def test_health_endpoint(self):
        r = httpx.get(f"{BASE_URL}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_submit_and_poll(self, headers):
        payload = {
            "full_name": "Integration Test User",
            "email": "integration@test.example.com",
            "phone": "9876543210",
            "dob": "1990-01-01",
            "pan_number": "ABCDE1234F",
            "doc_type": "PAN",
            "doc_image_b64": "",    # no image → ML service uses fallback
            "selfie_b64": "",
            "device": {"fingerprint": "test_fp_abc123", "user_agent": "pytest"},
            "behavioural": {"keystroke_intervals": [120, 130, 115], "paste_count": 0},
        }
        r = httpx.post(f"{BASE_URL}/v1/assessments", json=payload, headers=headers)
        assert r.status_code == 202, r.text
        job_id = r.json()["job_id"]
        assert job_id

        result = _wait_for_result(job_id, headers)
        assert "trust_score" in result
        assert result["decision"] in ("APPROVE", "STEP_UP", "MANUAL_REVIEW", "REJECT")
        assert 0.0 <= result["trust_score"] <= 100.0
        assert "reason_codes" in result

    def test_unauthenticated_request_rejected(self):
        r = httpx.post(f"{BASE_URL}/v1/assessments", json={})
        assert r.status_code == 401

    def test_audit_log_accessible(self, headers):
        r = httpx.get(f"{BASE_URL}/v1/audit", headers=headers)
        assert r.status_code == 200

    def test_metrics_accessible(self, headers):
        r = httpx.get(f"{BASE_URL}/v1/metrics", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "total_assessments" in data


@pytest.mark.integration
class TestChannelIntegration:
    def test_channel_assess_queued(self):
        payload = {
            "full_name": "Channel Test",
            "email": "channel@test.example.com",
            "phone": "9800000001",
            "dob": "1985-06-15",
            "pan_number": "XYZPQ5678A",
        }
        r = httpx.post(
            f"{BASE_URL}/v1/channel/assess",
            json=payload,
            headers={"X-TL-API-Key": "ch_mobile_prod_key_001"},
        )
        assert r.status_code == 202
        assert "assessment_id" in r.json()
