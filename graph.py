from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver

from state import TripPlanState
from agents.research_agent import research_agent
from agents.local_insight_agent import local_insight_agent
from agents.budget_agent import budget_agent
from agents.flight_agent import flight_agent
from agents.aggregator_agent import aggregator_agent


def human_review_node(state: TripPlanState) -> dict:
    decision = interrupt(
        {
            "reason": state.get("review_reason"),
            "draft_itinerary": state.get("draft_itinerary"),
        }
    )
    return {"user_decision": decision}


MIN_ACTIVITIES_PER_DAY = 1


def _trim_to_budget(itinerary: dict, scoring_report: dict, budget_cap: float) -> dict:
    """Drop the lowest-scored activities one at a time until the itinerary fits the
    activities budget (or until every day is down to MIN_ACTIVITIES_PER_DAY, whichever
    comes first - a day is never emptied out entirely)."""
    days = itinerary.get("days", [])
    all_activities = [(day["day"], act) for day in days for act in day.get("activities", [])]
    all_activities.sort(
        key=lambda pair: scoring_report.get(f"Day {pair[0]}", {}).get(pair[1]["name"], {}).get("overall", 0)
    )

    total = sum(act.get("estimated_cost_usd", 0) for _, act in all_activities)
    remaining_per_day = {day["day"]: len(day.get("activities", [])) for day in days}
    names_to_drop = set()

    for day_num, act in all_activities:
        if total <= budget_cap:
            break
        if remaining_per_day[day_num] <= MIN_ACTIVITIES_PER_DAY:
            continue
        names_to_drop.add(act["name"])
        total -= act.get("estimated_cost_usd", 0)
        remaining_per_day[day_num] -= 1

    for day in days:
        day["activities"] = [a for a in day["activities"] if a["name"] not in names_to_drop]

    new_total = sum(a.get("estimated_cost_usd", 0) for day in days for a in day["activities"])
    trimmed_scoring_report = {
        day_key: {name: scores for name, scores in day_scores.items() if name not in names_to_drop}
        for day_key, day_scores in scoring_report.items()
    }
    return {
        "itinerary": {
            "days": days,
            "total_estimated_activity_cost": round(new_total, 2),
            "trimmed_activities": sorted(names_to_drop),
            "still_over_budget": new_total > budget_cap,
        },
        "scoring_report": trimmed_scoring_report,
    }


def finalize_node(state: TripPlanState) -> dict:
    itinerary = state.get("draft_itinerary", {})
    decision = state.get("user_decision")
    scoring_report = state.get("scoring_report", {})

    if state.get("needs_user_review") and decision == "cut_activities":
        budget_cap = state.get("budget_breakdown", {}).get("activities", 0)
        trimmed = _trim_to_budget(itinerary, scoring_report, budget_cap)
        itinerary = trimmed["itinerary"]
        scoring_report = trimmed["scoring_report"]

    return {"final_itinerary": itinerary, "scoring_report": scoring_report}


def _route_after_aggregate(state: TripPlanState) -> str:
    return "human_review" if state.get("needs_user_review") else "finalize"


def build_graph():
    graph = StateGraph(TripPlanState)
    graph.add_node("research", research_agent)
    graph.add_node("local_insight", local_insight_agent)
    graph.add_node("budget", budget_agent)
    graph.add_node("flight", flight_agent)
    graph.add_node("aggregate", aggregator_agent)
    graph.add_node("human_review", human_review_node)
    graph.add_node("finalize", finalize_node)

    # Fan-out: these 4 run in parallel, each writing only to its own state key.
    graph.add_edge(START, "research")
    graph.add_edge(START, "local_insight")
    graph.add_edge(START, "budget")
    graph.add_edge(START, "flight")

    # Fan-in: aggregate only runs once all 4 branches complete.
    graph.add_edge("research", "aggregate")
    graph.add_edge("local_insight", "aggregate")
    graph.add_edge("budget", "aggregate")
    graph.add_edge("flight", "aggregate")

    graph.add_conditional_edges(
        "aggregate", _route_after_aggregate, {"human_review": "human_review", "finalize": "finalize"}
    )
    graph.add_edge("human_review", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=MemorySaver())
