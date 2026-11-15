"""Optional Ollama adapter. No transcript persistence or external provider fallback."""
import os

import httpx

SYSTEM_PROMPT = (
    "You are an optional, local wellbeing conversation assistant for a crew member. "
    "Offer brief, respectful listening and practical reflection questions. Do not diagnose, "
    "score, classify risk, interpret screening results, prescribe treatment, or claim to have "
    "contacted anyone. Do not request identifying details. If the person says they feel unsafe "
    "or may harm themselves or someone else, encourage them to contact a nearby trusted crew "
    "member and use their onboard support procedure now. State uncertainty plainly. This is "
    "not a substitute for qualified human support."
)
RESPONSE_TIMEOUT_SECONDS = 45


class ModelUnavailable(Exception):
    pass


def configured():
    return bool(os.environ.get("CHATBOT_LOCAL_MODEL_URL", "").strip() and
                os.environ.get("CHATBOT_LOCAL_MODEL_NAME", "").strip())


def enabled():
    return (os.environ.get("CHATBOT_CONVERSATION_ENABLED", "false").strip().lower() in ("1", "true", "yes")
            and configured())


def language():
    value = os.environ.get("CHATBOT_CONVERSATION_LANGUAGE", "en").strip().lower()
    return value if value in ("en", "es") else "en"


def reply(messages):
    base_url = os.environ.get("CHATBOT_LOCAL_MODEL_URL", "").strip().rstrip("/")
    model = os.environ.get("CHATBOT_LOCAL_MODEL_NAME", "").strip()
    if not base_url or not model:
        raise ModelUnavailable("Local conversation is not configured.")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT +
                      (" Respond in Spanish." if language() == "es" else " Respond in English.")},
                     *[item.model_dump() for item in messages]],
        "stream": False,
        "options": {"temperature": 0.35, "num_predict": 400},
    }
    try:
        response = httpx.post(base_url + "/api/chat", json=payload, timeout=RESPONSE_TIMEOUT_SECONDS)
        response.raise_for_status()
        text = response.json().get("message", {}).get("content", "").strip()
    except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
        raise ModelUnavailable("The configured local model did not return a usable reply.") from exc
    if not text:
        raise ModelUnavailable("The configured local model returned an empty reply.")
    return text[:4000]
