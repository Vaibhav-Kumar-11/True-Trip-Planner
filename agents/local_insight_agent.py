from state import TripPlanState, SearchFinding
from tools.search import search
from tools.llm import invoke_json

PROMPT_TEMPLATE = """You are a local-insight travel assistant. Below are raw Reddit/Quora/travel-blog \
search snippets about {destination}.
Extract genuine local recommendations: hidden gems, overrated/touristy spots to reconsider, and any \
safety notes (e.g. areas to avoid at night).

Search snippets:
{snippets}

Respond with ONLY valid JSON in this exact shape:
{{"summary": "2-3 sentence overview", "hidden_gems": ["..."], "overrated_or_unsafe": ["..."]}}
"""


def local_insight_agent(state: TripPlanState) -> dict:
    destination = state["destination"]
    results = search(f"{destination} reddit hidden gems avoid tourist trap local recommendations")
    used_fallback_query = False

    if not results:
        # Fallback: the niche query found nothing. Broaden scope rather than depending on the
        # Research agent's output - that agent runs in parallel with this one and its result
        # isn't guaranteed to exist yet.
        results = search(f"things to do in {destination}")
        used_fallback_query = True

    if not results:
        finding: SearchFinding = {
            "summary": f"No local insight data found for {destination}.",
            "sources": [],
            "confidence": "low",
        }
        return {"local_insights": finding}

    snippets = "\n\n".join(f"- {r.get('title', '')}: {r.get('content', '')[:400]}" for r in results[:5])
    parsed = invoke_json(PROMPT_TEMPLATE.format(destination=destination, snippets=snippets))

    summary = parsed.get("summary", "Summary unavailable.")
    if parsed.get("hidden_gems"):
        summary += "\n\nHidden gems: " + ", ".join(parsed["hidden_gems"])
    if parsed.get("overrated_or_unsafe"):
        summary += "\n\nOverrated/unsafe notes: " + ", ".join(parsed["overrated_or_unsafe"])
    if used_fallback_query:
        summary += "\n\n(fallback: no Reddit/Quora-specific results, broadened to a general query)"

    finding: SearchFinding = {
        "summary": summary,
        "sources": [r.get("url", "") for r in results[:5]],
        "confidence": "low" if (used_fallback_query or not parsed) else "high",
    }
    return {"local_insights": finding}
