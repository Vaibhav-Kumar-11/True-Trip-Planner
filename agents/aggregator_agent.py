from state import TripPlanState
from tools.llm import invoke_json

BUDGET_OVERRUN_THRESHOLD_PCT = 15

TIME_OF_DAY_BASE_FEASIBILITY = {"morning": 1.0, "afternoon": 0.95, "evening": 0.85, "night": 0.7}
MAX_COMFORTABLE_ACTIVITIES_PER_DAY = 3

ITINERARY_PROMPT = """You are an itinerary-planning assistant building a {num_days}-day trip to \
{destination} for {adults} adult(s) and {kids} kid(s).
Traveler interests: {interests}.

Mainstream research findings:
{research}

Local/hidden-gem insights:
{local_insights}

Using both sources, draft a day-by-day itinerary. For each activity, estimate a realistic cost in \
USD per person, categorize it as one of: scenic, culture, shopping, nightlife, note the time of day \
(morning/afternoon/evening/night), and rate authenticity_score from 0.0 to 1.0 - how much of a \
local hidden-gem this is (near 1.0) versus a mainstream/touristy pick (near 0.0), based on whether \
it came from the local-insight source or the mainstream research source and how often the mainstream \
source repeats it.

Respond with ONLY valid JSON in this exact shape:
{{"days": [{{"day": 1, "activities": [{{"name": "...", "description": "...", \
"estimated_cost_usd": 20, "category": "scenic", "authenticity_score": 0.75, "time_of_day": "morning"}}]}}]}}
"""


def _score_activity(
    activity: dict,
    interest_tags: list[str],
    per_day_activity_budget: float,
    has_kids: bool,
    activities_today: int,
) -> dict:
    cost = activity.get("estimated_cost_usd", 0)
    budget_fit = 1 - max(0, cost - per_day_activity_budget) / max(per_day_activity_budget, 1)
    budget_fit = round(max(0.0, min(1.0, budget_fit)), 2)

    authenticity = round(max(0.0, min(1.0, float(activity.get("authenticity_score", 0.5)))), 2)
    interest_fit = 1.0 if activity.get("category") in interest_tags else 0.3

    feasibility = TIME_OF_DAY_BASE_FEASIBILITY.get(activity.get("time_of_day"), 0.9)
    if has_kids and activity.get("time_of_day") == "night":
        feasibility *= 0.3
    if activities_today > MAX_COMFORTABLE_ACTIVITIES_PER_DAY:
        feasibility *= 0.85  # day is overpacked, harder to actually fit everything in
    logistics_feasibility = round(min(1.0, feasibility), 2)

    scores = {
        "budget_fit": budget_fit,
        "authenticity": authenticity,
        "interest_fit": interest_fit,
        "logistics_feasibility": logistics_feasibility,
    }
    scores["overall"] = round(sum(scores.values()) / 4, 2)
    return scores


def aggregator_agent(state: TripPlanState) -> dict:
    research = state.get("research_findings") or {"summary": "No research data."}
    local_insights = state.get("local_insights") or {"summary": "No local insight data."}
    budget = state.get("budget_breakdown") or {"activities": state["total_budget"] * 0.25}
    interest_tags = state.get("interest_tags") or []

    prompt = ITINERARY_PROMPT.format(
        num_days=state["num_days"],
        destination=state["destination"],
        adults=state["adults"],
        kids=state["kids"],
        interests=", ".join(interest_tags) or "no specific preference",
        research=research["summary"],
        local_insights=local_insights["summary"],
    )
    parsed = invoke_json(prompt, temperature=0.4)
    days = parsed.get("days", [])

    per_day_activity_budget = budget["activities"] / max(state["num_days"], 1)
    has_kids = state["kids"] > 0

    # scoring_report is keyed by day so the UI can render one table per day.
    scoring_report = {}
    total_estimated_cost = 0.0
    for day in days:
        activities = day.get("activities", [])
        day_scores = {}
        for activity in activities:
            scores = _score_activity(activity, interest_tags, per_day_activity_budget, has_kids, len(activities))
            day_scores[activity["name"]] = scores
            total_estimated_cost += activity.get("estimated_cost_usd", 0)
            activity["is_hidden_gem"] = scores["authenticity"] >= 0.6
        scoring_report[f"Day {day['day']}"] = day_scores

    overrun_pct = (
        (total_estimated_cost - budget["activities"]) / budget["activities"] * 100
        if budget.get("activities") else 0
    )
    needs_review = overrun_pct > BUDGET_OVERRUN_THRESHOLD_PCT
    review_reason = (
        f"Estimated activity costs (${total_estimated_cost:.0f}) exceed the activities budget "
        f"(${budget['activities']:.0f}) by {overrun_pct:.0f}%. Cut activities, raise the budget, "
        "or shorten the trip?"
        if needs_review else None
    )

    return {
        "draft_itinerary": {"days": days, "total_estimated_activity_cost": round(total_estimated_cost, 2)},
        "scoring_report": scoring_report,
        "needs_user_review": needs_review,
        "review_reason": review_reason,
    }
