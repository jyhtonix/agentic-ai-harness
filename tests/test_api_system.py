"""Tests for the CTF Platform API and Session Management Layer.

Covers:
  - Health endpoint
  - Challenge discovery API
  - Challenge execution API (non-blocking)
  - Session management
  - Report retrieval
  - Authentication
  - Error handling
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient
import yaml

from api.app import create_app
from api.auth import AuthProvider
from api.session_manager import SessionManager
from api.schemas.session import SessionState

from challenges_engine.loader import ChallengeLoader
from challenges_engine.models import ChallengeDefinition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_test_challenge_yaml(tmp_dir: Path, challenge_id: str) -> Path:
    c_dir = tmp_dir / challenge_id
    (c_dir / "files").mkdir(parents=True, exist_ok=True)
    (c_dir / "hints").mkdir(parents=True, exist_ok=True)
    (c_dir / "expected").mkdir(parents=True, exist_ok=True)

    (c_dir / "expected" / "flag.txt").write_text("CTF{test_flag}")
    (c_dir / "hints" / "hint1.txt").write_text("Look at the metadata")
    (c_dir / "files" / "sample.txt").write_text("test data")

    data = {
        "name": challenge_id.replace("_", " ").title(),
        "category": "steganography" if "stego" in challenge_id else "malware",
        "difficulty": "beginner",
        "description": f"A test challenge called {challenge_id}",
        "required_skills": ["steganography-basics"] if "stego" in challenge_id else ["malware-analysis-basics"],
        "allowed_tools": ["strings", "exiftool"],
        "verification": {"type": "exact_flag"},
        "flag_format": "CTF{.*}",
        "expected_flag": "CTF{test_flag}",
    }

    with open(c_dir / "challenge.yaml", "w") as f:
        yaml.dump(data, f)
    return c_dir


class FakeSupervisor:
    def __init__(self):
        self.run = AsyncMock(return_value={
            "request": "Solve the challenge",
            "analysis": "Test analysis",
            "plan": [{"agent": "analyst", "task": "analyze", "depends_on": []}],
            "agent_results": [{"agent": "analyst", "status": "completed", "response": "CTF{test_flag}"}],
            "verification": {"status": "passed", "confidence_score": 0.9, "findings": []},
            "learning_report": {
                "challenge_id": "abc123",
                "challenge_summary": "Test challenge",
                "skills_used": [{"name": "stego-basics", "category": "steganography"}],
                "skills_mastered": ["stego-basics"],
                "skills_needing_improvement": [],
                "difficulty_estimate": "beginner",
                "recommendations": ["Keep practicing"],
                "student_report": "=== LEARNING REPORT ===\nSkills Practiced:\n  - stego-basics\n\n=== END REPORT ===",
                "instructor_summary": "=== INSTRUCTOR SUMMARY ===\nSkills Used (1):\n  - stego-basics\n\n=== END INSTRUCTOR SUMMARY ===",
            },
            "flag_verification": {"status": "PASS", "method": "exact_flag", "detail": "Matched", "student_flag": "CTF{test_flag}"},
            "challenge": {"name": "Stego Test", "category": "steganography", "difficulty": "beginner"},
            "final_response": "Challenge solved.",
        })


# ===================================================================
# App fixture
# ===================================================================

@pytest.fixture
def app_with_loader():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        create_test_challenge_yaml(d, "stego_test_001")
        create_test_challenge_yaml(d, "malware_test_001")
        loader = ChallengeLoader(challenges_dir=str(d))
        supervisor_factory = lambda: FakeSupervisor()
        app = create_app(
            debug=True,
            challenge_loader=loader,
            supervisor_factory=supervisor_factory,
        )
        yield app


@pytest.fixture
def app_without_loader():
    app = create_app(debug=True)
    yield app


@pytest.fixture
def client(app_with_loader):
    with TestClient(app_with_loader) as c:
        yield c


@pytest.fixture
def client_no_loader(app_without_loader):
    with TestClient(app_without_loader) as c:
        yield c


# ===================================================================
# Health
# ===================================================================

class TestHealth:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.3.5"


# ===================================================================
# Challenge API
# ===================================================================

class TestChallengeAPI:
    def test_list_challenges(self, client):
        response = client.get("/api/v1/challenges")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        names = [c["name"] for c in data]
        assert "Stego Test 001" in names

    def test_list_challenges_filter_by_category(self, client):
        response = client.get("/api/v1/challenges?category=malware")
        assert response.status_code == 200
        data = response.json()
        assert all(c["category"] == "malware" for c in data)

    def test_list_challenges_filter_by_difficulty(self, client):
        response = client.get("/api/v1/challenges?difficulty=beginner")
        assert response.status_code == 200
        data = response.json()
        assert all(c["difficulty"] == "beginner" for c in data)

    def test_list_challenges_filter_by_skill(self, client):
        response = client.get("/api/v1/challenges?skill=steganography")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_list_challenges_no_loader(self, client_no_loader):
        response = client_no_loader.get("/api/v1/challenges")
        assert response.status_code == 503

    def test_challenge_summary_has_expected_fields(self, client):
        response = client.get("/api/v1/challenges")
        data = response.json()
        for c in data:
            assert "id" in c
            assert "name" in c
            assert "category" in c
            assert "difficulty" in c


# ===================================================================
# Execution API
# ===================================================================

class TestExecutionAPI:
    def test_valid_challenge_accepted(self, client):
        response = client.post(
            "/api/v1/challenges/run",
            json={"challenge_id": "stego_test_001"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert data["status"] == "running"

    def test_invalid_challenge_rejected(self, client):
        response = client.post(
            "/api/v1/challenges/run",
            json={"challenge_id": "nonexistent_challenge"},
        )
        assert response.status_code == 404

    def test_no_loader_returns_503(self, client_no_loader):
        response = client_no_loader.post(
            "/api/v1/challenges/run",
            json={"challenge_id": "stego_test_001"},
        )
        assert response.status_code == 503

    def test_run_creates_session(self, client):
        response = client.post(
            "/api/v1/challenges/run",
            json={"challenge_id": "stego_test_001"},
        )
        data = response.json()
        session_id = data["session_id"]
        # Verify session was created
        status_resp = client.get(f"/api/v1/sessions/{session_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] in ("RUNNING", "COMPLETED")

    def test_run_with_custom_prompt(self, client):
        response = client.post(
            "/api/v1/challenges/run",
            json={"challenge_id": "stego_test_001", "user_prompt": "Find the hidden message"},
        )
        assert response.status_code == 201


# ===================================================================
# Session API
# ===================================================================

class TestSessionAPI:
    def test_get_session_status(self, client):
        create_resp = client.post(
            "/api/v1/challenges/run",
            json={"challenge_id": "stego_test_001"},
        )
        session_id = create_resp.json()["session_id"]

        status_resp = client.get(f"/api/v1/sessions/{session_id}")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["session_id"] == session_id
        assert data["status"] in ("RUNNING", "COMPLETED")

    def test_get_nonexistent_session(self, client):
        response = client.get("/api/v1/sessions/nonexistent")
        assert response.status_code == 404

    def test_session_includes_challenge_info(self, client):
        create_resp = client.post(
            "/api/v1/challenges/run",
            json={"challenge_id": "malware_test_001"},
        )
        session_id = create_resp.json()["session_id"]
        status_resp = client.get(f"/api/v1/sessions/{session_id}")
        data = status_resp.json()
        assert data["challenge"] == "malware_test_001"


# ===================================================================
# Report API
# ===================================================================

class TestReportAPI:
    def test_get_report_for_completed_session(self, client):
        create_resp = client.post(
            "/api/v1/challenges/run",
            json={"challenge_id": "stego_test_001"},
        )
        session_id = create_resp.json()["session_id"]

        # Wait briefly for async execution
        import time
        time.sleep(0.3)

        report_resp = client.get(f"/api/v1/reports/{session_id}")
        assert report_resp.status_code == 200
        data = report_resp.json()
        assert data["session_id"] == session_id
        assert "challenge" in data

    def test_get_report_nonexistent_session(self, client):
        response = client.get("/api/v1/reports/nonexistent")
        assert response.status_code == 404

    def test_report_includes_skills_and_recommendations(self, client):
        create_resp = client.post(
            "/api/v1/challenges/run",
            json={"challenge_id": "stego_test_001"},
        )
        session_id = create_resp.json()["session_id"]

        import time
        time.sleep(0.3)

        report_resp = client.get(f"/api/v1/reports/{session_id}")
        data = report_resp.json()
        assert "student_report" in data
        assert "instructor_summary" in data
        assert "skills_used" in data


# ===================================================================
# Session Manager Unit Tests
# ===================================================================

class TestSessionManager:
    def test_create_session(self):
        mgr = SessionManager()
        session = mgr.create_session("test-challenge")
        assert session.session_id is not None
        assert session.challenge_id == "test-challenge"
        assert session.status == "CREATED"

    def test_get_session(self):
        mgr = SessionManager()
        created = mgr.create_session("test-challenge")
        retrieved = mgr.get_session(created.session_id)
        assert retrieved is not None
        assert retrieved.session_id == created.session_id

    def test_get_missing_session(self):
        mgr = SessionManager()
        assert mgr.get_session("nonexistent") is None

    def test_update_status(self):
        mgr = SessionManager()
        session = mgr.create_session("test")
        mgr.update_status(session.session_id, "RUNNING")
        assert mgr.get_session(session.session_id).status == "RUNNING"

    def test_set_result(self):
        mgr = SessionManager()
        session = mgr.create_session("test")
        mgr.set_result(session.session_id, {"key": "value"})
        assert mgr.get_session(session.session_id).result == {"key": "value"}

    def test_set_error(self):
        mgr = SessionManager()
        session = mgr.create_session("test")
        mgr.set_error(session.session_id, "Something went wrong")
        s = mgr.get_session(session.session_id)
        assert s.status == "FAILED"
        assert s.error == "Something went wrong"

    def test_set_flag_result(self):
        mgr = SessionManager()
        session = mgr.create_session("test")
        mgr.set_flag_result(session.session_id, {"status": "PASS"})
        assert mgr.get_session(session.session_id).flag_result == {"status": "PASS"}

    def test_contains(self):
        mgr = SessionManager()
        s = mgr.create_session("test")
        assert s.session_id in mgr
        assert "nonexistent" not in mgr


# ===================================================================
# Auth Provider
# ===================================================================

class TestAuthProvider:
    @pytest.mark.asyncio
    async def test_anonymous_mode(self):
        auth = AuthProvider(mode="anonymous")
        ok, user = await auth.authenticate(None)
        assert ok is True
        assert user == "anonymous"

    @pytest.mark.asyncio
    async def test_api_key_valid(self):
        auth = AuthProvider(mode="api_key", api_key="test-key-123")
        ok, user = await auth.authenticate("test-key-123")
        assert ok is True
        assert user == "api_key_user"

    @pytest.mark.asyncio
    async def test_api_key_invalid(self):
        auth = AuthProvider(mode="api_key", api_key="test-key-123")
        ok, user = await auth.authenticate("wrong-key")
        assert ok is False

    @pytest.mark.asyncio
    async def test_api_key_missing(self):
        auth = AuthProvider(mode="api_key", api_key="test-key-123")
        ok, user = await auth.authenticate(None)
        assert ok is False
        assert "Missing" in user

    def test_is_anonymous(self):
        assert AuthProvider(mode="anonymous").is_anonymous is True
        assert AuthProvider(mode="api_key").is_anonymous is False


# ===================================================================
# Security / Error handling
# ===================================================================

class TestSecurity:
    def test_invalid_json_body_returns_422(self, client):
        response = client.post(
            "/api/v1/challenges/run",
            data="not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_empty_challenge_id_rejected(self, client):
        response = client.post(
            "/api/v1/challenges/run",
            json={"challenge_id": ""},
        )
        assert response.status_code == 422

    def test_unknown_route_returns_404(self, client):
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404
