from agents.aggregator_agent import _score_activity


def test_budget_fit_is_full_when_well_under_budget():
    activity = {"estimated_cost_usd": 10, "category": "scenic", "time_of_day": "morning"}
    scores = _score_activity(activity, ["scenic"], per_day_activity_budget=100, has_kids=False, activities_today=1)
    assert scores["budget_fit"] == 1.0


def test_budget_fit_drops_when_over_budget():
    activity = {"estimated_cost_usd": 200, "category": "scenic", "time_of_day": "morning"}
    scores = _score_activity(activity, ["scenic"], per_day_activity_budget=100, has_kids=False, activities_today=1)
    assert scores["budget_fit"] < 1.0


def test_interest_fit_matches_selected_tags():
    activity = {"estimated_cost_usd": 10, "category": "shopping", "time_of_day": "morning"}
    matched = _score_activity(activity, ["shopping"], 100, False, 1)
    unmatched = _score_activity(activity, ["culture"], 100, False, 1)
    assert matched["interest_fit"] == 1.0
    assert unmatched["interest_fit"] == 0.3


def test_logistics_feasibility_penalizes_night_activities_with_kids():
    activity = {"estimated_cost_usd": 10, "category": "nightlife", "time_of_day": "night"}
    with_kids = _score_activity(activity, ["nightlife"], 100, has_kids=True, activities_today=1)
    without_kids = _score_activity(activity, ["nightlife"], 100, has_kids=False, activities_today=1)
    assert with_kids["logistics_feasibility"] < without_kids["logistics_feasibility"]


def test_logistics_feasibility_penalizes_overpacked_days():
    activity = {"estimated_cost_usd": 10, "category": "scenic", "time_of_day": "morning"}
    light_day = _score_activity(activity, ["scenic"], 100, False, activities_today=2)
    packed_day = _score_activity(activity, ["scenic"], 100, False, activities_today=5)
    assert packed_day["logistics_feasibility"] < light_day["logistics_feasibility"]


def test_authenticity_is_clamped_to_valid_range():
    over_range = {"estimated_cost_usd": 10, "category": "scenic", "time_of_day": "morning", "authenticity_score": 1.5}
    under_range = {"estimated_cost_usd": 10, "category": "scenic", "time_of_day": "morning", "authenticity_score": -0.5}
    assert _score_activity(over_range, [], 100, False, 1)["authenticity"] == 1.0
    assert _score_activity(under_range, [], 100, False, 1)["authenticity"] == 0.0


def test_overall_is_average_of_four_dimensions():
    activity = {"estimated_cost_usd": 10, "category": "scenic", "time_of_day": "morning", "authenticity_score": 0.8}
    scores = _score_activity(activity, ["scenic"], 100, False, 1)
    expected = round((scores["budget_fit"] + scores["authenticity"] + scores["interest_fit"] + scores["logistics_feasibility"]) / 4, 2)
    assert scores["overall"] == expected
