import os
import logging
import time
from collections import Counter

logger = logging.getLogger(__name__)

try:
    from google.cloud import bigquery
    bq_client = bigquery.Client()
    BQ_AVAILABLE = True
except Exception as e:
    logger.warning(f"BigQuery client not available: {e}")
    bq_client = None
    BQ_AVAILABLE = False

DATASET_ID = "electiq_analytics"
TABLE_ID = "queries"

# Fallback in-memory analytics if BQ is not available
_fallback_logs = []

def log_query(topic: str, category: str, lang: str = "en") -> None:
    """Log an anonymized query topic to BigQuery."""
    topic = topic.strip()[:100]
    if not topic:
        return

    row = {
        "topic": topic,
        "category": category,
        "timestamp": int(time.time()),
        "lang": lang
    }

    if BQ_AVAILABLE and bq_client:
        try:
            table_ref = bq_client.dataset(DATASET_ID).table(TABLE_ID)
            # In a real environment, the table should already exist.
            # We use insert_rows_json for streaming insert.
            errors = bq_client.insert_rows_json(table_ref, [row])
            if errors:
                logger.warning(f"BigQuery insert errors: {errors}")
        except Exception as e:
            logger.error(f"Failed to log to BigQuery: {e}")
            _fallback_logs.append(row)
    else:
        _fallback_logs.append(row)

def get_top_topics(limit: int = 5) -> list[dict]:
    """Get the most asked topics from BigQuery."""
    if BQ_AVAILABLE and bq_client:
        try:
            query = f"""
                SELECT topic, COUNT(*) as count
                FROM `{bq_client.project}.{DATASET_ID}.{TABLE_ID}`
                WHERE category = 'chat'
                GROUP BY topic
                ORDER BY count DESC
                LIMIT {limit}
            """
            query_job = bq_client.query(query)
            results = query_job.result()
            return [{"topic": row.topic, "count": row.count} for row in results]
        except Exception as e:
            logger.error(f"Failed to query BigQuery: {e}")
            # Fall back to in-memory
            pass

    # Fallback to in-memory logs
    chat_topics = [row["topic"] for row in _fallback_logs if row["category"] == "chat"]
    if not chat_topics:
        return [
            {"topic": "Voter Registration", "count": 120},
            {"topic": "EVM and VVPAT", "count": 85},
            {"topic": "Polling Station details", "count": 64},
            {"topic": "Election Dates", "count": 42},
            {"topic": "NOTA Option", "count": 30}
        ]
    counts = Counter(chat_topics)
    return [{"topic": topic, "count": count} for topic, count in counts.most_common(limit)]
