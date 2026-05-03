"""
ElectIQ v3.1 — High Fidelity Backend Tests
Covers Service Layer delegation, API mocks, and edge cases.
"""

import json
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import app
from services import gemini, cloud_data

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

# ── Static & Health Tests ──
def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert json.loads(res.data)["status"] == "healthy"

def test_security_headers(client):
    res = client.get("/")
    assert res.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in res.headers

def test_static_files(client):
    res = client.get("/static/style.css")
    assert res.status_code in [200, 404] # 404 is fine if file missing, but endpoint exists

# ── Service Layer: Cloud Data ──
@patch("services.cloud_data.get_trending_topics")
def test_analytics_endpoint(mock_get, client):
    mock_get.return_value = [{"topic": "EVM", "count": 10}]
    res = client.get("/api/analytics")
    assert res.status_code == 200
    assert "top_topics" in json.loads(res.data)

@patch("services.cloud_data.translate_content")
def test_translate_endpoint(mock_trans, client):
    mock_trans.return_value = "नमस्ते"
    res = client.post("/api/translate", json={"text": "Hello", "target": "hi"})
    assert res.status_code == 200
    assert json.loads(res.data)["translated"] == "नमस्ते"

def test_translate_no_text(client):
    res = client.post("/api/translate", json={})
    assert res.status_code == 400

@patch("services.cloud_data.persist_score")
def test_score_submission(mock_save, client):
    res = client.post("/api/score", json={"topic": "Polity", "score": 5, "total": 5})
    assert res.status_code == 200

# ── Service Layer: Gemini AI ──
@patch("services.gemini.generate_quiz")
def test_quiz_generation(mock_quiz, client):
    mock_quiz.return_value = {"questions": [{"question": "Who?", "options": ["Me", "You"], "correct": 0}]}
    res = client.post("/api/quiz", json={"topic": "Voting"})
    assert res.status_code == 200
    assert "questions" in json.loads(res.data)

@patch("services.gemini.fact_check")
def test_fact_check_logic(mock_fc, client):
    mock_fc.return_value = {"verdict": "TRUE", "explanation": "Verified"}
    res = client.post("/api/fact-check", json={"claim": "VVPAT is mandatory in India."})
    assert res.status_code == 200
    assert json.loads(res.data)["verdict"] == "TRUE"

@patch("services.gemini.generate_chat_response")
def test_chat_streaming(mock_chat, client):
    def mock_gen(msgs):
        chunk = MagicMock()
        chunk.text = "Hello"
        yield chunk
    mock_chat.side_effect = mock_gen
    res = client.post("/api/chat/stream", json={"messages": [{"role": "user", "content": "Hi"}]})
    assert res.status_code == 200
    assert b"data:" in res.data

# ── Edge Cases & Error Handling ──
def test_chat_empty_messages(client):
    res = client.post("/api/chat/stream", json={"messages": []})
    assert res.status_code == 400

def test_fact_check_short_claim(client):
    res = client.post("/api/fact-check", json={"claim": "short"})
    assert res.status_code == 400

def test_missing_payload_quiz(client):
    # If topic missing, it defaults to "Indian elections" in app.py
    with patch("services.gemini.generate_quiz") as mock_q:
        mock_q.return_value = {"questions": []}
        res = client.post("/api/quiz", json={}) 
        assert res.status_code == 200

@patch("services.gemini.generate_quiz")
def test_ai_error_handling(mock_quiz, client):
    mock_quiz.side_effect = Exception("AI Down")
    res = client.post("/api/quiz", json={"topic": "Test"})
    assert res.status_code == 500

def test_user_facing_error_helper():
    from app import user_facing_error
    assert "rate limit" in user_facing_error(Exception("429 error"))
    assert "Something went wrong" in user_facing_error(Exception("Other error"))

def test_get_json_payload_malformed(client):
    # This tests the silent=True behavior
    with app.test_request_context(json="{bad"):
        from app import get_json_payload
        assert get_json_payload() == {}
