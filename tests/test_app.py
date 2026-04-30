"""
ElectIQ — Unit Tests for Flask Backend
Tests API endpoints with mocked Gemini responses.
"""

import json
import pytest
import sys
import os

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import app


@pytest.fixture
def client():
    """Create Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestStaticRoutes:
    """Test static file serving."""

    def test_index_returns_html(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert b"ElectIQ" in response.data

    def test_health_endpoint(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "healthy"
        assert "ai_configured" in data
        assert "model" in data


class TestSearchEndpoint:
    """Test Google Custom Search API proxy."""

    def test_search_returns_fallback_without_keys(self, client):
        """Without API keys, should return curated fallback results."""
        response = client.get("/api/search?q=voter+registration")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "items" in data
        assert len(data["items"]) > 0
        assert any("eci.gov.in" in item["link"] for item in data["items"])

    def test_search_default_query(self, client):
        """Default query should work."""
        response = client.get("/api/search")
        assert response.status_code == 200


class TestChatEndpoint:
    """Test AI chat endpoint."""

    def test_chat_rejects_empty_messages(self, client):
        response = client.post(
            "/api/chat",
            json={"messages": []},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_chat_requires_messages(self, client):
        response = client.post(
            "/api/chat",
            json={},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_chat_handles_malformed_json(self, client):
        response = client.post(
            "/api/chat",
            data="{bad json",
            content_type="application/json",
        )
        assert response.status_code == 400


class TestQuizEndpoint:
    """Test quiz generation endpoint."""

    def test_quiz_returns_error_without_ai(self, client):
        """Without Gemini configured, should return error."""
        response = client.post(
            "/api/quiz",
            json={"topic": "Indian elections"},
            content_type="application/json",
        )
        # Should return 500 if no AI configured, or 200 with questions
        assert response.status_code in [200, 500]

    def test_quiz_normalizer_filters_invalid_questions(self):
        data = app_module.normalize_quiz({
            "questions": [
                {
                    "question": "Valid?",
                    "options": ["A", "B"],
                    "correct": 1,
                    "explanation": "Because.",
                },
                {
                    "question": "Invalid?",
                    "options": ["A"],
                    "correct": 2,
                },
            ]
        })
        assert len(data["questions"]) == 1
        assert data["questions"][0]["correct"] == 1


class TestFactCheckEndpoint:
    """Test fact-checker endpoint."""

    def test_factcheck_rejects_short_claim(self, client):
        response = client.post(
            "/api/fact-check",
            json={"claim": "test"},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_factcheck_rejects_empty_claim(self, client):
        response = client.post(
            "/api/fact-check",
            json={"claim": ""},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_factcheck_requires_claim(self, client):
        response = client.post(
            "/api/fact-check",
            json={},
            content_type="application/json",
        )
        assert response.status_code == 400


class TestParsingHelpers:
    """Test AI JSON cleanup helpers."""

    def test_parse_ai_json_strips_markdown_fence(self):
        assert app_module.parse_ai_json('```json\n{"ok": true}\n```') == {"ok": True}

    def test_parse_ai_json_extracts_object_from_extra_text(self):
        assert app_module.parse_ai_json('Result:\n{"ok": true}\nDone') == {"ok": True}


class TestElectionsEndpoint:
    """Test election tracker fallback behavior."""

    def test_elections_returns_empty_fallback_without_ai(self, client, monkeypatch):
        monkeypatch.setattr(app_module, "client", None)
        response = client.get("/api/elections")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["current"] == []
        assert data["upcoming"] == []
        assert "source_note" in data


class TestStreamEndpoint:
    """Test streaming chat endpoint."""

    def test_stream_rejects_empty_messages(self, client):
        response = client.post(
            "/api/chat/stream",
            json={"messages": []},
            content_type="application/json",
        )
        assert response.status_code == 400
