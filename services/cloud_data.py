import os
import logging
from analytics import get_top_topics, log_query as bq_log_query
from translate import translate_text
from firebase_db import save_quiz_score

logger = logging.getLogger(__name__)

def get_trending_topics(limit=5):
    """
    Fetches the most popular election topics from BigQuery.
    Returns hardcoded fallbacks if the API is unavailable.
    """
    try:
        return get_top_topics(limit=limit)
    except Exception as e:
        logger.error(f"Service Layer: Error fetching trending topics: {e}")
        return []

def translate_content(text, target_lang="hi"):
    """
    Translates textual content for localized frontend display.
    Delegates to Google Cloud Translate API.
    """
    if not text:
        return text
    try:
        return translate_text(text, target_lang=target_lang)
    except Exception as e:
        logger.error(f"Service Layer: Translation error: {e}")
        return text

def persist_score(topic, score, total):
    """
    Saves quiz performance metrics to Firestore.
    """
    try:
        save_quiz_score(topic, score, total)
        return True
    except Exception as e:
        logger.error(f"Service Layer: Persistence error: {e}")
        return False

def log_query(text, category):
    """
    Logs user interactions for BigQuery analytics.
    """
    try:
        bq_log_query(text, category)
    except Exception as e:
        logger.error(f"Service Layer: Analytics logging error: {e}")
