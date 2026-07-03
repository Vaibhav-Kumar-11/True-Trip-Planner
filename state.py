from typing import TypedDict, Literal, Optional


class SearchFinding(TypedDict):
    """Common shape returned by any agent that does a web search."""
    summary: str
    sources: list[str]
    confidence: Literal["high", "low"]  # "low" = fallback data, not the real thing


class BudgetBreakdown(TypedDict):
    stay: float
    food: float
    transport: float
    activities: float
    per_person: float


class TripPlanState(TypedDict):
    # --- user inputs (filled once, at the start, never overwritten) ---
    destination: str
    start_date: str
    end_date: str
    num_days: int
    adults: int
    kids: int
    total_budget: float
    interest_tags: list[str]  # e.g. ["scenic", "culture", "shopping", "nightlife"]

    # --- one dedicated output slot per specialist agent ---
    research_findings: Optional[SearchFinding]
    local_insights: Optional[SearchFinding]
    budget_breakdown: Optional[BudgetBreakdown]
    flight_estimate: Optional[SearchFinding]

    # --- aggregator's output ---
    draft_itinerary: Optional[dict]
    scoring_report: Optional[dict]

    # --- human-in-the-loop ---
    needs_user_review: bool
    review_reason: Optional[str]
    user_decision: Optional[str]

    final_itinerary: Optional[dict]
