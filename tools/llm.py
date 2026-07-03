import os
import re
import json
import time
from groq import RateLimitError
from langchain_groq import ChatGroq

MODEL_NAME = "llama-3.3-70b-versatile"
MAX_RATE_LIMIT_ATTEMPTS = 3


def get_llm(temperature: float = 0.3) -> ChatGroq:
    return ChatGroq(model=MODEL_NAME, api_key=os.environ["GROQ_API_KEY"], temperature=temperature)


def _invoke_with_backoff(llm: ChatGroq, prompt: str):
    """Groq's free tier has a tokens-per-minute cap. On a 429, wait for the
    window to clear (using the wait time Groq suggests in the error message
    when available) and retry, instead of failing the whole run."""
    for attempt in range(MAX_RATE_LIMIT_ATTEMPTS):
        try:
            return llm.invoke(prompt)
        except RateLimitError as e:
            if attempt == MAX_RATE_LIMIT_ATTEMPTS - 1:
                raise
            match = re.search(r"try again in (?:(\d+)m)?(\d+(?:\.\d+)?)s", str(e))
            if match:
                minutes = float(match.group(1)) if match.group(1) else 0
                wait_seconds = minutes * 60 + float(match.group(2)) + 1
            else:
                wait_seconds = 5 * (attempt + 1)
            time.sleep(wait_seconds)


def invoke_json(prompt: str, temperature: float = 0.3) -> dict:
    """Ask the LLM for JSON. If the response fails to parse, retry once with a
    stricter instruction before giving up (the "retries" failure-handling mechanism)."""
    llm = get_llm(temperature)
    response = _invoke_with_backoff(llm, prompt)
    parsed = _try_parse(response.content)
    if parsed is not None:
        return parsed

    retry_prompt = (
        prompt
        + "\n\nYour previous response was not valid JSON. "
        "Respond with ONLY valid JSON and nothing else - no explanation, no markdown fences."
    )
    response = _invoke_with_backoff(llm, retry_prompt)
    parsed = _try_parse(response.content)
    return parsed if parsed is not None else {}


def _try_parse(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
