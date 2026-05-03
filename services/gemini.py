import os
import json
import logging
import re
from google import genai
from google.genai import types
import config

logger = logging.getLogger(__name__)

# Config
GCP_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
GCP_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-south1")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_ID = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Client init
try:
    if GCP_PROJECT:
        client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
        logger.info(f"Gemini (Vertex AI) initialized: {GCP_PROJECT}")
    elif GEMINI_API_KEY:
        client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Gemini (AI Studio) initialized.")
    else:
        client = None
        logger.warning("No Gemini credentials found.")
except Exception as e:
    logger.error(f"Failed to init Gemini client: {e}")
    client = None

def convert_messages(messages: list) -> list:
    """Convert frontend message format to Gemini Content format."""
    contents = []
    for msg in messages[-config.MAX_CHAT_MESSAGES:]:
        role = "model" if msg.get("role") == "assistant" else "user"
        text = str(msg.get("content", ""))[:config.MAX_MESSAGE_CHARS]
        contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
    return contents

def clean_ai_json(text: str) -> str:
    """Extract JSON object from markdown or raw text."""
    if not text: return ""
    cleaned = text.strip()
    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL | re.IGNORECASE)
    if fence_match: cleaned = fence_match.group(1).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1 and end > start: cleaned = cleaned[start:end + 1]
    return cleaned

def generate_chat_response(messages: list):
    """Generate a streaming or non-streaming chat response."""
    if not client: raise RuntimeError("Gemini client not initialized")
    contents = convert_messages(messages)
    config_dict = {
        "system_instruction": config.SYSTEM_PROMPT,
        "tools": [types.Tool(google_search_retrieval=types.GoogleSearchRetrieval())],
        "temperature": 0.3,
    }
    return client.models.generate_content_stream(model=MODEL_ID, contents=contents, config=config_dict)

def generate_quiz(topic: str):
    """Generate a quiz object using structured JSON output."""
    if not client: raise RuntimeError("Gemini client not initialized")
    prompt = config.QUIZ_PROMPT_TEMPLATE.format(topic=topic)
    res = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "system_instruction": "You are a professional civic educator. Output ONLY valid JSON.",
        }
    )
    return json.loads(clean_ai_json(res.text))

def fact_check(claim: str):
    """Generate a structured fact-check verdict."""
    if not client: raise RuntimeError("Gemini client not initialized")
    prompt = config.FACT_CHECK_PROMPT_TEMPLATE.format(claim=claim)
    res = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "tools": [types.Tool(google_search_retrieval=types.GoogleSearchRetrieval())],
            "system_instruction": "You are a non-partisan election fact-checker. Be concise and cite rules.",
        }
    )
    return json.loads(clean_ai_json(res.text))
