from state import TripPlanState, BudgetBreakdown

CATEGORY_SPLIT = {"stay": 0.40, "food": 0.20, "transport": 0.15, "activities": 0.25}


def budget_agent(state: TripPlanState) -> dict:
    total = state["total_budget"]
    travelers = max(state["adults"] + state["kids"], 1)

    breakdown: BudgetBreakdown = {
        "stay": round(total * CATEGORY_SPLIT["stay"], 2),
        "food": round(total * CATEGORY_SPLIT["food"], 2),
        "transport": round(total * CATEGORY_SPLIT["transport"], 2),
        "activities": round(total * CATEGORY_SPLIT["activities"], 2),
        "per_person": round(total / travelers, 2),
    }
    return {"budget_breakdown": breakdown}
