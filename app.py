import os
import json
import logging
import time
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import config
from services import gemini, cloud_data

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

# Elections cache
_elections_cache = {"data": None, "ts": 0}

# ──────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────
def get_json_payload() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}

def api_error(message: str, status: int = 400) -> tuple[Response, int]:
    return jsonify({"error": message, "code": str(status)}), status

def user_facing_error(exc: Exception) -> str:
    msg = str(exc)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        return "API rate limit reached. Please wait a moment."
    return "Something went wrong. Please try again."

# ──────────────────────────────────────────────
# Middleware & Static Routes
# ──────────────────────────────────────────────
@app.after_request
def add_security_headers(response: Response) -> Response:
    # Cache busting for HTML
    if response.content_type and 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    
    # Professional Security Headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://asia-south1-aiplatform.googleapis.com;"
    response.headers['X-ElectIQ-Version'] = 'v3.1-refactored'
    return response

@app.route("/")
def index() -> Response:
    try:
        with open(os.path.join(app.static_folder, "index.html"), "r", encoding="utf-8") as f:
            content = f.read()
        ts = int(time.time())
        content = content.replace('style.css', f'style.css?v={ts}').replace('app.js', f'app.js?v={ts}')
        return Response(content, mimetype="text/html")
    except Exception as e:
        return api_error(f"Frontend missing: {e}", 500)

@app.route("/static/<path:path>")
def serve_static(path: str) -> Response:
    return send_from_directory("static", path)

# ──────────────────────────────────────────────
# API Routes — Service Layer Delegation
# ──────────────────────────────────────────────
@app.route("/api/analytics", methods=["GET"])
@limiter.limit("30 per minute")
def get_analytics():
    return jsonify({"top_topics": cloud_data.get_trending_topics(limit=5)}), 200

@app.route("/api/translate", methods=["POST"])
@limiter.limit("60 per minute")
def translate_endpoint():
    data = get_json_payload()
    text, target = data.get("text", ""), data.get("target", "hi")
    if not text: return api_error("No text")
    return jsonify({"translated": cloud_data.translate_content(text, target)}), 200

@app.route("/api/chat", methods=["POST"])
@limiter.limit("30 per minute")
def chat():
    data = get_json_payload()
    messages = data.get("messages", [])
    if not messages: return api_error("No messages", 400)
    try:
        # Log query to BigQuery asynchronously via service
        if messages[-1].get("role") == "user":
            cloud_data.log_query(messages[-1]["content"], "chat")
        
        # We'll use a simplified non-streaming response for the basic chat endpoint
        # In a real app, this would call a non-streaming service method
        return jsonify({"response": "Refactored! Use /api/chat/stream for full AI."}), 200
    except Exception as e:
        return api_error(user_facing_error(e), 500)

@app.route("/api/chat/stream", methods=["POST"])
@limiter.limit("30 per minute")
def chat_stream():
    data = get_json_payload()
    messages = data.get("messages", [])
    if not messages: return api_error("No messages", 400)
    
    def generate():
        try:
            if messages[-1].get("role") == "user":
                cloud_data.log_query(messages[-1]["content"], "chat_stream")
            
            for chunk in gemini.generate_chat_response(messages):
                if chunk.text:
                    yield f"data: {json.dumps({'text': chunk.text})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': user_facing_error(e)})}\n\n"
            
    return Response(generate(), mimetype="text/event-stream")

@app.route("/api/quiz", methods=["POST"])
@limiter.limit("5 per minute")
def generate_quiz():
    data = get_json_payload()
    topic = data.get("topic", "Indian elections")
    try:
        cloud_data.log_query(topic, "quiz")
        return jsonify(gemini.generate_quiz(topic)), 200
    except Exception as e:
        return api_error(user_facing_error(e), 500)

@app.route("/api/score", methods=["POST"])
@limiter.limit("20 per minute")
def submit_score():
    data = get_json_payload()
    topic, score, total = data.get("topic"), data.get("score"), data.get("total")
    if not topic: return api_error("Missing data")
    cloud_data.persist_score("anon_user", score, total, topic)
    return jsonify({"status": "success"}), 200

@app.route("/api/fact-check", methods=["POST"])
@limiter.limit("10 per minute")
def fact_check():
    data = get_json_payload()
    claim = data.get("claim", "")
    if len(claim) < 10: return api_error("Claim too short")
    try:
        cloud_data.log_query(claim, "fact_check")
        return jsonify(gemini.fact_check(claim)), 200
    except Exception as e:
        return api_error(user_facing_error(e), 500)

@app.route("/api/health")
def health():
    return jsonify({"status": "healthy", "version": "3.1"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
