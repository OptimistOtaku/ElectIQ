"""
ElectIQ — India Election Process Education Assistant
Backend powered by Google Gemini 3 Flash + Google Cloud
"""

import os
import json
import logging
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
    for msg in messages:
        role = msg.get("role", "user")
        # Gemini uses 'model' instead of 'assistant'
        if role == "assistant":
            role = "model"
        text = msg.get("content", "")
        contents.append(
            types.Content(role=role, parts=[types.Part(text=text)])
        )
    return contents


# ──────────────────────────────────────────────
# Routes — Static
# ──────────────────────────────────────────────
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
    data = request.json
    messages = data.get("messages", [])

    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    if not client:
        return jsonify({"error": "Gemini AI not configured. Set GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT."}), 500

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
        error_msg = str(e)
        if '429' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg:
            error_msg = 'API rate limit reached. Please wait a moment and try again.'
        logger.error(f"Chat error: {e}")
        return jsonify({"error": error_msg}), 500


@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """Streaming chat endpoint with Google Search grounding via SSE."""
    data = request.json
    messages = data.get("messages", [])

    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    if not client:
        return jsonify({"error": "Gemini AI not configured"}), 500

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
            error_msg = str(e)
            if '429' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg:
                error_msg = 'API rate limit reached. Please wait a moment and try again.'
            yield f"data: {json.dumps({'error': error_msg})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


# ──────────────────────────────────────────────
# Routes — Quiz Generation
# ──────────────────────────────────────────────
@app.route("/api/quiz", methods=["POST"])
def generate_quiz():
    """Generate AI quiz questions via Gemini 3 Flash."""
    if not client:
        return jsonify({"error": "Gemini AI not configured"}), 500

    topic = request.json.get("topic", "Indian elections")

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
        text = response.text.strip()
        # Strip potential markdown fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        return jsonify(json.loads(text))
    except json.JSONDecodeError as e:
        logger.error(f"Quiz JSON parse error: {e}, raw: {response.text[:200]}")
        return jsonify({"error": "Failed to parse quiz questions. Please try again."}), 500
    except Exception as e:
        error_msg = str(e)
        # Clean up rate limit errors for user display
        if '429' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg:
            error_msg = 'API rate limit reached. Please wait a moment and try again.'
        logger.error(f"Quiz error: {e}")
        return jsonify({"error": error_msg}), 500


# ──────────────────────────────────────────────
# Routes — Fact Checker (Gemini + Google Search)
# ──────────────────────────────────────────────
@app.route("/api/fact-check", methods=["POST"])
def fact_check():
    """Fact-check an election claim using Gemini with Google Search grounding."""
    claim = request.json.get("claim", "")
    if not claim or len(claim.strip()) < 10:
        return jsonify({"error": "Please provide a meaningful claim to verify (at least 10 characters)."}), 400

    if not client:
        return jsonify({"error": "Gemini AI not configured"}), 500

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
        text = response.text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        result = json.loads(text)

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
        error_msg = str(e)
        if '429' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg:
            error_msg = 'API rate limit reached. Please wait a moment and try again.'
        logger.error(f"Fact-check error: {e}")
        return jsonify({"error": error_msg}), 500


# ──────────────────────────────────────────────
# Routes — Google Custom Search
# ──────────────────────────────────────────────
@app.route("/api/search", methods=["GET"])
def search():
    """Search for election-related content via Google Custom Search API."""
    query = request.args.get("q", "India election process")
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
        return jsonify(resp.json())
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({"error": str(e)}), 500


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
