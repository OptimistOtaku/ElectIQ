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

# ──────────────────────────────────────────────
# App Configuration
# ──────────────────────────────────────────────
app = Flask(__name__, static_folder="static")
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
ELECTIONS_CACHE_TTL = 3600  # seconds
MAX_CHAT_MESSAGES = 20
MAX_MESSAGE_CHARS = 4000
MAX_TOPIC_CHARS = 120
MAX_CLAIM_CHARS = 2000

CURATED_SEARCH_RESULTS = [
    {
        "title": "Election Commission of India",
        "link": "https://eci.gov.in",
        "snippet": "Official website of the Election Commission of India - schedules, results, and notifications.",
    },
    {
        "title": "National Voters' Service Portal",
        "link": "https://www.nvsp.in",
        "snippet": "Register to vote, update details, and check voter card status online.",
    },
    {
        "title": "Voter Helpline Portal",
        "link": "https://voters.eci.gov.in",
        "snippet": "Find your polling booth, check your name in the electoral roll, and get assistance.",
    },
    {
        "title": "PRS Legislative Research",
        "link": "https://prsindia.org",
        "snippet": "Non-partisan analysis of Parliament, bills, and election data for Indian citizens.",
    },
]

EMPTY_ELECTIONS_RESPONSE = {
    "current": [],
    "upcoming": [],
    "next_major_event": None,
    "source_note": "Live election data is unavailable. Check eci.gov.in for official schedules.",
}

# ──────────────────────────────────────────────
# System Prompts
# ──────────────────────────────────────────────
SYSTEM_PROMPT = """You are ElectIQ, an expert civic education assistant specializing in the Indian election process. You help citizens — especially first-time voters — understand how elections work in India.

You have deep knowledge of:
- Election Commission of India (ECI) structure and role
- Types of elections: Lok Sabha, Rajya Sabha, State Legislative Assembly (Vidhan Sabha), Panchayat, Municipal
- The full election lifecycle: Model Code of Conduct, nomination, campaigning, polling, counting, results
- Voter registration (Form 6), EPIC (Voter ID), and the NVSP/Voter Helpline 1950
- Electronic Voting Machines (EVMs) and VVPAT
- Reservation of constituencies (SC/ST)
- Role of political parties, symbols, and NOTA
- Election timelines and schedules announced by ECI
- How to find your polling booth, check voter list, etc.

Personality: Warm, clear, non-partisan, encouraging civic participation. Always explain things in simple language. Use examples relevant to Indian voters.

Format your responses with:
- Clear headings using **bold**
- Numbered or bulleted steps where appropriate
- Emoji to make content engaging 🗳️
- Always end with a helpful tip or call to action

Never express political opinions or favor any party. Stay strictly informational and neutral."""

FACT_CHECK_PROMPT = """You are ElectIQ Fact-Checker, a rigorous and neutral election fact verification assistant for India.

Your task: Analyze the given claim about Indian elections and provide a fact-check verdict.

Rules:
1. Be strictly factual and non-partisan
2. Use your knowledge of Indian election law, ECI rules, and constitutional provisions
3. Cite specific articles, sections, or official sources when possible
4. Consider the claim's context and nuance

Return your response in this EXACT JSON format (no markdown fences, no extra text):
{
  "verdict": "TRUE" | "FALSE" | "MISLEADING" | "PARTIALLY TRUE" | "UNVERIFIED",
  "verdict_emoji": "✅" | "❌" | "⚠️" | "🔶" | "❓",
  "summary": "One-line summary of the verdict",
  "explanation": "Detailed explanation (2-3 paragraphs) with specific references to laws, ECI guidelines, or constitutional provisions",
  "sources": ["Source 1 description", "Source 2 description"],
  "related_facts": ["Related fact 1", "Related fact 2"]
}"""


# ──────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────
def convert_messages(messages):
    """Convert frontend message format to Gemini Content format."""
    contents = []
    for msg in messages[-MAX_CHAT_MESSAGES:]:
        role = msg.get("role", "user")
        role = "model" if role == "assistant" else "user"
        text = str(msg.get("content", ""))[:MAX_MESSAGE_CHARS]
        contents.append(
            types.Content(role=role, parts=[types.Part(text=text)])
        )
    return contents


def get_json_payload():
    """Return JSON body as a dict without raising on malformed or missing JSON."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def api_error(message, status=400):
    return jsonify({"error": message}), status


def clean_ai_json(text):
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


def parse_ai_json(text):
    return json.loads(clean_ai_json(text))


def normalize_quiz(data):
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


def normalize_elections(data):
    if not isinstance(data, dict):
        raise ValueError("Election response must be an object")

    return {
        "current": data.get("current", []) if isinstance(data.get("current", []), list) else [],
        "upcoming": data.get("upcoming", []) if isinstance(data.get("upcoming", []), list) else [],
        "next_major_event": data.get("next_major_event") if isinstance(data.get("next_major_event"), dict) else None,
    }


def user_facing_error(exc, fallback="Something went wrong. Please try again."):
    error_msg = str(exc) or fallback
    if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
        return "API rate limit reached. Please wait a moment and try again."
    return error_msg


# ──────────────────────────────────────────────
# Routes — Static
# ──────────────────────────────────────────────
@app.after_request
def add_cache_headers(response):
    """Prevent browser caching of HTML pages so deployments take effect immediately."""
    if response.content_type and 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    response.headers['X-ElectIQ-Version'] = '2026-04-30-v2'
    return response


@app.route("/")
def index():
    """Serve the main SPA frontend."""
    return send_from_directory("static", "index.html")


@app.route("/static/<path:path>")
def serve_static(path):
    """Serve static assets (icons, manifest, etc.)."""
    return send_from_directory("static", path)


# ──────────────────────────────────────────────
# Routes — AI Chat
# ──────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def chat():
    """Non-streaming chat endpoint powered by Gemini 2.5 Flash with Google Search grounding."""
    data = get_json_payload()
    messages = data.get("messages", [])

    if not isinstance(messages, list) or not messages:
        return api_error("No messages provided")

    if not client:
        return api_error("Gemini AI not configured. Set GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT.", 500)

    try:
        contents = convert_messages(messages)
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=2048,
                temperature=0.7,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        return jsonify({"response": response.text})
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return api_error(user_facing_error(e), 500)


@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """Streaming chat endpoint with Google Search grounding via SSE."""
    data = get_json_payload()
    messages = data.get("messages", [])

    if not isinstance(messages, list) or not messages:
        return api_error("No messages provided")

    if not client:
        return api_error("Gemini AI not configured", 500)

    def generate():
        try:
            contents = convert_messages(messages)
            response_stream = client.models.generate_content_stream(
                model=MODEL_ID,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
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
# Routes — Quiz Generation
# ──────────────────────────────────────────────
@app.route("/api/quiz", methods=["POST"])
def generate_quiz():
    """Generate AI quiz questions via Gemini 2.5 Flash."""
    if not client:
        return api_error("Gemini AI not configured", 500)

    data = get_json_payload()
    topic = str(data.get("topic", "Indian elections")).strip()[:MAX_TOPIC_CHARS] or "Indian elections"

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

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=4096,
                temperature=0.8,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        return jsonify(normalize_quiz(parse_ai_json(response.text)))
    except json.JSONDecodeError as e:
        logger.error(f"Quiz JSON parse error: {e}, raw: {response.text[:200]}")
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
def fact_check():
    """Fact-check an election claim using Gemini with Google Search grounding."""
    data = get_json_payload()
    claim = str(data.get("claim", "")).strip()[:MAX_CLAIM_CHARS]
    if not claim or len(claim.strip()) < 10:
        return api_error("Please provide a meaningful claim to verify (at least 10 characters).")

    if not client:
        return api_error("Gemini AI not configured", 500)

    try:
        # Use Gemini with Google Search grounding for fact-checking
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=f"Fact-check this claim about Indian elections:\n\n\"{claim}\"",
            config=types.GenerateContentConfig(
                system_instruction=FACT_CHECK_PROMPT,
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
        return jsonify(result)

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
        })
    except Exception as e:
        logger.error(f"Fact-check error: {e}")
        return api_error(user_facing_error(e), 500)


# ──────────────────────────────────────────────
# Routes — Google Custom Search
# ──────────────────────────────────────────────
@app.route("/api/search", methods=["GET"])
def search():
    """Search for election-related content via Google Custom Search API."""
    query = (request.args.get("q") or "India election process").strip()[:120]
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_CX:
        # Graceful fallback with curated results
        return jsonify({
            "items": [
                {
                    "title": "Election Commission of India",
                    "link": "https://eci.gov.in",
                    "snippet": "Official website of the Election Commission of India — schedules, results, and notifications.",
                },
                {
                    "title": "National Voters' Service Portal",
                    "link": "https://www.nvsp.in",
                    "snippet": "Register to vote, update details, and check voter card status online.",
                },
                {
                    "title": "Voter Helpline Portal",
                    "link": "https://voters.eci.gov.in",
                    "snippet": "Find your polling booth, check your name in the electoral roll, and get assistance.",
                },
                {
                    "title": "PRS Legislative Research",
                    "link": "https://prsindia.org",
                    "snippet": "Non-partisan analysis of Parliament, bills, and election data for Indian citizens.",
                },
            ]
        })

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
        return jsonify(resp.json())
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({
            "items": CURATED_SEARCH_RESULTS,
            "warning": "Live search unavailable; showing curated official resources.",
        })


# ──────────────────────────────────────────────
# Routes — Live Election Data (Gemini + Search Grounding)
# ──────────────────────────────────────────────
@app.route("/api/elections", methods=["GET"])
def get_elections():
    """Return live current + upcoming Indian election data via Gemini 2.5 Flash with Google Search grounding."""
    global _elections_cache

    # Serve from cache if fresh
    if _elections_cache["data"] and (time.time() - _elections_cache["ts"]) < ELECTIONS_CACHE_TTL:
        return jsonify(_elections_cache["data"])

    if not client:
        return jsonify(EMPTY_ELECTIONS_RESPONSE)

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
        return jsonify(data)

    except json.JSONDecodeError as e:
        logger.error(f"Elections JSON parse error: {e}")
        return jsonify(EMPTY_ELECTIONS_RESPONSE)
    except ValueError as e:
        logger.error(f"Elections validation error: {e}")
        return jsonify(EMPTY_ELECTIONS_RESPONSE)
    except Exception as e:
        logger.error(f"Elections error: {e}")
        return jsonify(EMPTY_ELECTIONS_RESPONSE)


# ──────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────
@app.route("/api/health")
def health():
    """Health check endpoint for Cloud Run."""
    return jsonify({
        "status": "healthy",
        "ai_configured": client is not None,
        "model": MODEL_ID,
        "search_configured": bool(GOOGLE_SEARCH_API_KEY),
    })


# ──────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")
