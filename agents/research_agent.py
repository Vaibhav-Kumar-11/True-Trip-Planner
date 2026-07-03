from state import TripPlanState, SearchFinding
from tools.search import search
from tools.llm import invoke_json

PROMPT_TEMPLATE = """You are a travel research assistant. Below are raw web search snippets about \
popular things to do in {destination}.
Summarize the 5-8 most commonly recommended attractions/activities travelers do here.

Search snippets:
{snippets}

Respond with ONLY valid JSON in this exact shape:
{{"summary": "2-3 sentence overview", "highlights": ["activity 1", "activity 2"]}}
"""


def research_agent(state: TripPlanState) -> dict:
    destination = state["destination"]
    results = search(f"best things to do in {destination} popular itinerary attractions")

    if not results:
        finding: SearchFinding = {
            "summary": f"No mainstream research data found for {destination}.",
            "sources": [],
            "confidence": "low",
        }
        return {"research_findings": finding}

    snippets = "\n\n".join(f"- {r.get('title', '')}: {r.get('content', '')[:400]}" for r in results[:5])
    parsed = invoke_json(PROMPT_TEMPLATE.format(destination=destination, snippets=snippets))

    summary = parsed.get("summary", "Summary unavailable.")
    if parsed.get("highlights"):
        summary += "\n\nHighlights: " + ", ".join(parsed["highlights"])

    finding: SearchFinding = {
        "summary": summary,
        "sources": [r.get("url", "") for r in results[:5]],
        "confidence": "high" if parsed else "low",
    }
    return {"research_findings": finding}
