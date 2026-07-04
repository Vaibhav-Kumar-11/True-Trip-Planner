from agents.budget_agent import budget_agent


def test_category_split_sums_to_total():
    state = {"total_budget": 1000.0, "adults": 2, "kids": 0}
    result = budget_agent(state)["budget_breakdown"]
    category_total = result["stay"] + result["food"] + result["transport"] + result["activities"]
    assert category_total == 1000.0


def test_per_person_scales_with_traveler_count():
    solo = budget_agent({"total_budget": 1000.0, "adults": 1, "kids": 0})["budget_breakdown"]
    family = budget_agent({"total_budget": 1000.0, "adults": 2, "kids": 2})["budget_breakdown"]
    assert solo["per_person"] == 1000.0
    assert family["per_person"] == 250.0


def test_zero_travelers_does_not_divide_by_zero():
    result = budget_agent({"total_budget": 500.0, "adults": 0, "kids": 0})["budget_breakdown"]
    assert result["per_person"] == 500.0  # falls back to treating it as 1 traveler
