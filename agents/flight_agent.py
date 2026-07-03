from state import TripPlanState, SearchFinding
from tools.search import search
from tools.llm import invoke_json

PROMPT_TEMPLATE = """You are a flight-price research assistant. Below are raw web search snippets \
about flight prices/routes to {destination} around {start_date} for {travelers} traveler(s).
Estimate a realistic price RANGE (not a single number) per traveler in USD, and note common \
routes/layovers mentioned.

Search snippets:
{snippets}

Respond with ONLY valid JSON in this exact shape:
{{"summary": "2-3 sentence overview", "price_range_usd": "e.g. 450-700", "common_routes": ["..."]}}
"""


def flight_agent(state: TripPlanState) -> dict:
    destination = state["destination"]
    travelers = state["adults"] + state["kids"]
    results = search(f"flight prices to {destination} {state['start_date']} round trip cost")

    if not results:
        finding: SearchFinding = {
            "summary": f"No flight price data found for {destination}.",
            "sources": [],
            "confidence": "low",
        }
        return {"flight_estimate": {**finding, "price_range_usd": "unknown", "common_routes": []}}

    snippets = "\n\n".join(f"- {r.get('title', '')}: {r.get('content', '')[:400]}" for r in results[:5])
    parsed = invoke_json(
        PROMPT_TEMPLATE.format(
            destination=destination,
            start_date=state["start_date"],
            travelers=travelers,
            snippets=snippets,
        )
    )

    finding: SearchFinding = {
        "summary": parsed.get("summary", "Summary unavailable."),
        "sources": [r.get("url", "") for r in results[:5]],
        "confidence": "high" if parsed else "low",
    }
    # Kept as structured fields (not folded into the summary text) so the UI can tabulate them.
    return {
        "flight_estimate": {
            **finding,
            "price_range_usd": parsed.get("price_range_usd", "unknown"),
            "common_routes": parsed.get("common_routes", []),
        }
    }
