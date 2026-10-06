from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import logging
import os

import requests

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

SYSTEM_PROMPT = "You are a helpful assistant. Format answers in Markdown when useful."

# Bound cost and payload size
MAX_HISTORY_MESSAGES = 20
MAX_MESSAGE_LENGTH = 4000
MAX_CONTEXT_LENGTH = 20000
MAX_OUTPUT_TOKENS = 1024


def _clean_messages(raw_messages):
    """Validate client-sent history: [{"role": "user"|"assistant", "content": str}, ...]."""
    if not isinstance(raw_messages, list):
        return None
    messages = []
    for msg in raw_messages[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(msg, dict):
            return None
        role = msg.get('role')
        content = str(msg.get('content', '')).strip()
        if role not in ('user', 'assistant') or not content:
            return None
        messages.append({"role": role, "content": content[:MAX_MESSAGE_LENGTH]})
    if not messages or messages[-1]["role"] != "user":
        return None
    return messages


def _ask_gemini(system_prompt, messages):
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        headers={"x-goog-api-key": GEMINI_API_KEY},
        json={
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [
                {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                for m in messages
            ],
            "generationConfig": {"maxOutputTokens": MAX_OUTPUT_TOKENS, "temperature": 0.7},
        },
        timeout=60,
    )
    response.raise_for_status()
    parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(part.get("text", "") for part in parts).strip()


def _ask_openai(system_prompt, messages):
    import openai
    client = openai.Client(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "system", "content": system_prompt}, *messages],
        max_tokens=MAX_OUTPUT_TOKENS,
        temperature=0.7,
    )
    return (response.choices[0].message.content or "").strip()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chatbot_response(request):
    """
    Body: {"messages": [{"role": "user"|"assistant", "content": "..."}], "context": "optional text"}
    For backwards compatibility {"message": "..."} is also accepted.
    """
    if 'messages' in request.data:
        messages = _clean_messages(request.data.get('messages'))
    else:
        text = str(request.data.get('message', '')).strip()
        messages = [{"role": "user", "content": text[:MAX_MESSAGE_LENGTH]}] if text else None

    if not messages:
        return Response({"error": "A conversation ending with a user message is required"}, status=400)

    system_prompt = SYSTEM_PROMPT
    context = str(request.data.get('context') or '').strip()
    if context:
        system_prompt += (
            "\n\nUse the following context to answer the user's questions:\n"
            f"<context>\n{context[:MAX_CONTEXT_LENGTH]}\n</context>"
        )

    if not GEMINI_API_KEY and not OPENAI_API_KEY:
        logger.error("Neither GEMINI_API_KEY nor OPENAI_API_KEY is configured")
        return Response({"error": "The chatbot is not configured."}, status=500)

    try:
        if GEMINI_API_KEY:
            reply = _ask_gemini(system_prompt, messages)
        else:
            reply = _ask_openai(system_prompt, messages)
        return Response({"reply": reply or "Sorry, I couldn't generate a response."})
    except Exception:
        logger.exception("Chatbot request failed")
        return Response({"error": "The chatbot is unavailable right now. Please try again."}, status=502)
