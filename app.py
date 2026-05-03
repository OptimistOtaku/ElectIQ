"""
ElectIQ — India Election Process Education Assistant
Backend powered by Google Gemini 2.5 Flash + Google Cloud
"""

import os
import json
import logging
import re
import time
import requests as http_requests
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import config
import analytics
import translate
import firebase_db

# ──────────────────────────────────────────────
# App Configuration
# ──────────────────────────────────────────────
app = Flask(__name__, static_folder="static")
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate Limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# ──────────────────────────────────────────────
# Gemini AI Configuration
# ──────────────────────────────────────────────
try:
    from google import genai
    from google.genai import types

    GCP_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    GCP_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-south1")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

    if GCP_PROJECT:
        # Production: Vertex AI on Cloud Run (uses service account)
        client = genai.Client(
            vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION
        )
        logger.info(f"Gemini client initialized via Vertex AI (project={GCP_PROJECT})")
    elif GEMINI_API_KEY:
        # Development: Google AI Studio API key
        client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Gemini client initialized via AI Studio API key")
    else:
        client = None
        logger.warning("No Gemini credentials found. AI features will be disabled.")
except ImportError:
    client = None
    logger.warning("google-genai not installed. AI features disabled.")

MODEL_ID = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Google Custom Search config
GOOGLE_SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX", "")

# Elections cache — 1 hour TTL
_elections_cache = {"data": None, "ts": 0}

# ──────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────
def convert_messages(messages: list) -> list:
    """Convert frontend message format to Gemini Content format."""
    contents = []
    for msg in messages[-config.MAX_CHAT_MESSAGES:]:
        role = msg.get("role", "user")
        role = "model" if role == "assistant" else "user"
        text = str(msg.get("content", ""))[:config.MAX_MESSAGE_CHARS]
        contents.append(
            types.Content(role=role, parts=[types.Part(text=text)])
        )
    return contents


def get_json_payload() -> dict:
    """Return JSON body as a dict without raising on malformed or missing JSON."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def api_error(message: str, status: int = 400) -> tuple[Response, int]:
    return jsonify({"error": message, "code": str(status)}), status


def clean_ai_json(text: str) -> str:
    """Remove common markdown wrappers and extract the first JSON object."""
    if not text:
        raise json.JSONDecodeError("Empty response", "", 0)

    cleaned = text.strip()
    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL | re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start:end + 1]

    return cleaned


def parse_ai_json(text: str) -> dict:
    return json.loads(clean_ai_json(text))


def normalize_quiz(data: dict) -> dict:
    questions = data.get("questions", []) if isinstance(data, dict) else []
    normalized = []
    for item in questions:
        if not isinstance(item, dict):
            continue
        options = item.get("options", [])
        correct = item.get("correct", 0)
        if (
            isinstance(item.get("question"), str)
            and isinstance(options, list)
            and len(options) >= 2
            and isinstance(correct, int)
            and 0 <= correct < len(options)
        ):
            normalized.append({
                "question": item["question"],
                "options": [str(option) for option in options[:4]],
                "correct": correct,
                "explanation": str(item.get("explanation", "")),
            })

    if not normalized:
        raise ValueError("No valid quiz questions returned")
    return {"questions": normalized[:5]}


def normalize_elections(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Election response must be an object")

    return {
        "current": data.get("current", []) if isinstance(data.get("current", []), list) else [],
        "upcoming": data.get("upcoming", []) if isinstance(data.get("upcoming", []), list) else [],
        "next_major_event": data.get("next_major_event") if isinstance(data.get("next_major_event"), dict) else None,
    }


def user_facing_error(exc: Exception, fallback: str = "Something went wrong. Please try again.") -> str:
    error_msg = str(exc) or fallback
    if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
        return "API rate limit reached. Please wait a moment and try again."
    return error_msg


# ──────────────────────────────────────────────
# Routes — Static
# ──────────────────────────────────────────────
@app.after_request
def add_cache_headers(response: Response) -> Response:
    """Prevent browser caching of HTML pages so deployments take effect immediately."""
    if response.content_type and 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    response.headers['X-ElectIQ-Version'] = '2026-05-01-v3'
    return response

@app.route("/")
def index() -> Response:
    """Serve the main SPA frontend."""
    with open(os.path.join(app.static_folder, "index.html"), "r", encoding="utf-8") as f:
        content = f.read()
    # Dynamic cache busting for JS/CSS
    ts = int(time.time())
    content = content.replace('style.css', f'style.css?v={ts}')
    content = content.replace('app.js', f'app.js?v={ts}')
    return Response(content, mimetype="text/html")


@app.route("/static/<path:path>")
def serve_static(path: str) -> Response:
    """Serve static assets (icons, manifest, etc.)."""
    return send_from_directory("static", path)


# ──────────────────────────────────────────────
# Routes — Analytics & Translation
# ──────────────────────────────────────────────
@app.route("/api/analytics", methods=["GET"])
@limiter.limit("30 per minute")
def get_analytics() -> tuple[Response, int]:
    """Return top most asked topics from BigQuery."""
    return jsonify({"top_topics": analytics.get_top_topics(limit=5)}), 200

@app.route("/api/translate", methods=["POST"])
@limiter.limit("60 per minute")
def translate_endpoint() -> tuple[Response, int]:
    """Translate text using Google Translate API."""
    data = get_json_payload()
    text = data.get("text", "")
    target_lang = data.get("target", "hi")
    
    if not text:
        return api_error("No text provided", 400)
    
    try:
        translated = translate.translate_text(text, target_lang=target_lang)
        return jsonify({"translated": translated}), 200
    except Exception as e:
        logger.error(f"Translate endpoint error: {e}")
        return api_error(user_facing_error(e), 500)


# ──────────────────────────────────────────────
# Routes — AI Chat
# ──────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
@limiter.limit("10 per minute")
def chat() -> tuple[Response, int]:
    """Non-streaming chat endpoint powered by Gemini 2.5 Flash with Google Search grounding."""
    data = get_json_payload()
    messages = data.get("messages", [])

    if not isinstance(messages, list) or not messages:
        return api_error("No messages provided")

    if not client:
        return api_error("Gemini AI not configured. Set GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT.", 500)

    try:
        # Log to BigQuery
        last_user_msg = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), None)
        if last_user_msg:
            analytics.log_query(last_user_msg, "chat")

        contents = convert_messages(messages)
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=config.SYSTEM_PROMPT,
                max_output_tokens=2048,
                temperature=0.7,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        return jsonify({"response": response.text}), 200
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return api_error(user_facing_error(e), 500)


@app.route("/api/chat/stream", methods=["POST"])
@limiter.limit("10 per minute")
def chat_stream() -> Response:
    """Streaming chat endpoint with Google Search grounding via SSE."""
    data = get_json_payload()
    messages = data.get("messages", [])

    if not isinstance(messages, list) or not messages:
        return api_error("No messages provided")[0]

    if not client:
        return api_error("Gemini AI not configured", 500)[0]

    def generate():
        try:
            last_user_msg = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), None)
            if last_user_msg:
                analytics.log_query(last_user_msg, "chat_stream")

            contents = convert_messages(messages)
            response_stream = client.models.generate_content_stream(
                model=MODEL_ID,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=config.SYSTEM_PROMPT,
                    max_output_tokens=2048,
                    temperature=0.7,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )
            for chunk in response_stream:
                if chunk.text:
                    yield f"data: {json.dumps({'text': chunk.text})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': user_facing_error(e)})}\n\n"

    return Response(generate(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache"})


# ──────────────────────────────────────────────
# Routes — Quiz Generation & Scoring
# ──────────────────────────────────────────────
@app.route("/api/score", methods=["POST"])
@limiter.limit("20 per minute")
def submit_score() -> tuple[Response, int]:
    """Submit a quiz score to Firestore."""
    data = get_json_payload()
    topic = data.get("topic", "")
    score = data.get("score", 0)
    total = data.get("total", 0)
    
    if not topic:
        return api_error("Topic is required", 400)
        
    try:
        firebase_db.save_quiz_score(topic, score, total)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Score submit error: {e}")
        return api_error(user_facing_error(e), 500)

@app.route("/api/quiz", methods=["POST"])
@limiter.limit("5 per minute")
def generate_quiz() -> tuple[Response, int]:
    """Generate AI quiz questions via Gemini 2.5 Flash."""
    if not client:
        return api_error("Gemini AI not configured", 500)

    data = get_json_payload()
    topic = str(data.get("topic", "Indian elections")).strip()[:config.MAX_TOPIC_CHARS] or "Indian elections"

    try:
        analytics.log_query(topic, "quiz")

        prompt = f"""Generate 5 multiple-choice quiz questions about {topic} for Indian voters.
Return ONLY valid JSON with this exact structure:
{{
  "questions": [
    {{
      "question": "Question text here?",
      "options": ["A) Option1", "B) Option2", "C) Option3", "D) Option4"],
      "correct": 0,
      "explanation": "Brief explanation of correct answer"
    }}
  ]
}}
Make questions educational, factual, and relevant to Indian elections. No political bias.
Return ONLY the JSON object, no markdown code fences or extra text."""

        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=4096,
                temperature=0.8,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        return jsonify(normalize_quiz(parse_ai_json(response.text))), 200
    except json.JSONDecodeError as e:
        logger.error(f"Quiz JSON parse error: {e}")
        return api_error("Failed to parse quiz questions. Please try again.", 500)
    except ValueError as e:
        logger.error(f"Quiz validation error: {e}")
        return api_error("Quiz response was incomplete. Please try again.", 500)
    except Exception as e:
        logger.error(f"Quiz error: {e}")
        return api_error(user_facing_error(e), 500)


# ──────────────────────────────────────────────
# Routes — Fact Checker (Gemini + Google Search)
# ──────────────────────────────────────────────
@app.route("/api/fact-check", methods=["POST"])
@limiter.limit("5 per minute")
def fact_check() -> tuple[Response, int]:
    """Fact-check an election claim using Gemini with Google Search grounding."""
    data = get_json_payload()
    claim = str(data.get("claim", "")).strip()[:config.MAX_CLAIM_CHARS]
    if not claim or len(claim.strip()) < 10:
        return api_error("Please provide a meaningful claim to verify (at least 10 characters).")

    if not client:
        return api_error("Gemini AI not configured", 500)

    try:
        analytics.log_query(claim, "fact_check")

        # Use Gemini with Google Search grounding for fact-checking
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=f"Fact-check this claim about Indian elections:\n\n\"{claim}\"",
            config=types.GenerateContentConfig(
                system_instruction=config.FACT_CHECK_PROMPT,
                max_output_tokens=1500,
                temperature=0.3,  # Low temp for factual accuracy
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        result = parse_ai_json(response.text)

        # Extract grounding metadata if available
        grounding_sources = []
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, "grounding_metadata") and candidate.grounding_metadata:
                gm = candidate.grounding_metadata
                if hasattr(gm, "grounding_chunks") and gm.grounding_chunks:
                    for chunk in gm.grounding_chunks:
                        if hasattr(chunk, "web") and chunk.web:
                            grounding_sources.append({
                                "title": getattr(chunk.web, "title", "Source"),
                                "url": getattr(chunk.web, "uri", ""),
                            })

        result["grounding_sources"] = grounding_sources
        return jsonify(result), 200

    except json.JSONDecodeError:
        # If JSON parsing fails, return the raw text as explanation
        return jsonify({
            "verdict": "UNVERIFIED",
            "verdict_emoji": "❓",
            "summary": "Could not parse structured result",
            "explanation": response.text if response else "No response from AI",
            "sources": [],
            "related_facts": [],
            "grounding_sources": [],
        }), 200
    except Exception as e:
        logger.error(f"Fact-check error: {e}")
        return api_error(user_facing_error(e), 500)


# ──────────────────────────────────────────────
# Routes — Google Custom Search
# ──────────────────────────────────────────────
@app.route("/api/search", methods=["GET"])
@limiter.limit("20 per minute")
def search() -> tuple[Response, int]:
    """Search for election-related content via Google Custom Search API."""
    query = (request.args.get("q") or "India election process").strip()[:120]
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_CX:
        # Graceful fallback with curated results
        return jsonify({
            "items": config.CURATED_SEARCH_RESULTS
        }), 200

    try:
        resp = http_requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": GOOGLE_SEARCH_API_KEY,
                "cx": GOOGLE_SEARCH_CX,
                "q": query,
                "num": 5,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return jsonify(resp.json()), 200
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({
            "items": config.CURATED_SEARCH_RESULTS,
            "warning": "Live search unavailable; showing curated official resources.",
        }), 200


# ──────────────────────────────────────────────
# Routes — Live Election Data (Gemini + Search Grounding)
# ──────────────────────────────────────────────
@app.route("/api/elections", methods=["GET"])
@limiter.limit("30 per minute")
def get_elections() -> tuple[Response, int]:
    """Return live current + upcoming Indian election data via Gemini 2.5 Flash with Google Search grounding."""
    global _elections_cache

    # Serve from cache if fresh
    if _elections_cache["data"] and (time.time() - _elections_cache["ts"]) < config.ELECTIONS_CACHE_TTL:
        return jsonify(_elections_cache["data"]), 200

    if not client:
        return jsonify(config.EMPTY_ELECTIONS_RESPONSE), 200

    from datetime import datetime, timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))
    today = datetime.now(IST).strftime("%d %B %Y")
    prompt = f"""Today's date is exactly {today} (Indian Standard Time).

You MUST use Google Search to find the very latest information about Indian elections.

Return ONLY a valid JSON object (no markdown, no explanation, no ```json fences) with this structure:

{{
  "current": [
    {{
      "state": "State name in English",
      "state_hi": "State name in Hindi (Devanagari script)",
      "election_type": "Assembly" | "Lok Sabha" | "By-election" | "Panchayat",
      "status": "voting_today" | "voting_soon" | "counting" | "results_out",
      "status_label": "Short human-readable status in English",
      "polling_date": "Exact dates like '23 April 2026' or 'Phase 1: 09 Apr, Phase 2: 17 Apr'",
      "counting_date": "Exact date like '04 May 2026'",
      "total_seats": 123,
      "phases": 1,
      "note": "Brief context e.g. 'Phase 2 of 3' or 'Counting on 4 May'"
    }}
  ],
  "upcoming": [
    {{
      "state": "State name in English",
      "state_hi": "State name in Hindi (Devanagari script)",
      "election_type": "Assembly" | "Lok Sabha" | "By-election",
      "expected_period": "Month–Month YYYY",
      "total_seats": 123,
      "note": "Brief context"
    }}
  ],
  "next_major_event": {{
    "name": "Name of the ONE MOST IMPORTANT next election event from today {today} (e.g. 'Assam Assembly Election Counting'). Do NOT list multiple states.",
    "name_hi": "Same event name in Hindi",
    "date_iso": "YYYY-MM-DDTHH:MM:SS+05:30"
  }}
}}

IMPORTANT RULES:
- "current" = elections where ANY phase (notification, nomination, polling, counting) is happening within 30 days before or after today ({today}).
- "upcoming" = elections expected in the next 12 months that haven't started yet.
- next_major_event must be the chronologically NEXT single event AFTER today {today}. If multiple states vote/count on the same day, pick the most prominent one or summarize as 'Assembly Elections Voting (Phase X)'. Do NOT make the name a long list of states.
- All dates MUST be VERIFIED EXACT dates from the Election Commission of India (ECI) official schedule. If exact dates are not announced, use approximate periods (e.g., "Nov-Dec 2026").
- Do NOT include elections whose results were declared more than 30 days ago.
- Return ONLY the JSON object, nothing else."""

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=2048,
                temperature=0.1,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        data = normalize_elections(parse_ai_json(response.text))
        _elections_cache = {"data": data, "ts": time.time()}
        return jsonify(data), 200

    except json.JSONDecodeError as e:
        logger.error(f"Elections JSON parse error: {e}")
        return jsonify(config.EMPTY_ELECTIONS_RESPONSE), 200
    except ValueError as e:
        logger.error(f"Elections validation error: {e}")
        return jsonify(config.EMPTY_ELECTIONS_RESPONSE), 200
    except Exception as e:
        logger.error(f"Elections error: {e}")
        return jsonify(config.EMPTY_ELECTIONS_RESPONSE), 200


# ──────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────
@app.route("/api/health")
def health() -> tuple[Response, int]:
    """Health check endpoint for Cloud Run."""
    return jsonify({
        "status": "healthy",
        "ai_configured": client is not None,
        "model": MODEL_ID,
        "search_configured": bool(GOOGLE_SEARCH_API_KEY),
    }), 200


# ──────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")
