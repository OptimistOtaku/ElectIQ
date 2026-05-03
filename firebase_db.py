import logging
import time

logger = logging.getLogger(__name__)

try:
    from google.cloud import firestore
    db = firestore.Client()
    FIRESTORE_AVAILABLE = True
except Exception as e:
    logger.warning(f"Firestore not available: {e}")
    db = None
    FIRESTORE_AVAILABLE = False

COLLECTION_NAME = "quiz_scores"
_fallback_scores = []

def save_quiz_score(topic: str, score: int, total: int) -> None:
    """Save a quiz score to Firestore."""
    if not topic:
        return

    record = {
        "topic": topic,
        "score": score,
        "total": total,
        "timestamp": firestore.SERVER_TIMESTAMP if FIRESTORE_AVAILABLE else int(time.time()),
    }

    if FIRESTORE_AVAILABLE and db:
        try:
            db.collection(COLLECTION_NAME).add(record)
        except Exception as e:
            logger.error(f"Failed to save score to Firestore: {e}")
            _fallback_scores.append(record)
    else:
        _fallback_scores.append(record)

def get_high_scores(limit: int = 5) -> list[dict]:
    """Retrieve top recent quiz scores."""
    if FIRESTORE_AVAILABLE and db:
        try:
            query = db.collection(COLLECTION_NAME).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
            docs = query.stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error(f"Failed to fetch scores from Firestore: {e}")
            pass

    return _fallback_scores[-limit:]
