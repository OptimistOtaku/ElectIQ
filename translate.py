import os
import logging
import html

logger = logging.getLogger(__name__)

try:
    from google.cloud import translate_v2 as translate
    translate_client = translate.Client()
    TRANSLATE_AVAILABLE = True
except Exception as e:
    logger.warning(f"Google Cloud Translate not available: {e}")
    translate_client = None
    TRANSLATE_AVAILABLE = False

def translate_text(text: str, target_lang: str = "hi") -> str:
    """Translates text to the target language using Google Cloud Translate API."""
    if not text or not text.strip():
        return text

    if TRANSLATE_AVAILABLE and translate_client:
        try:
            # The translate API handles HTML nicely.
            result = translate_client.translate(text, target_language=target_lang)
            # Unescape HTML entities that might have been escaped during translation
            return html.unescape(result["translatedText"])
        except Exception as e:
            logger.error(f"Translation API error: {e}")
            return text
    else:
        # Fallback if API not available
        logger.debug(f"Translate API not available, returning original text.")
        return text
