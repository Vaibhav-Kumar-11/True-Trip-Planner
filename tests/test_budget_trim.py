from graph import _trim_to_budget


def _sample_itinerary():
    return {
        "days": [
            {"day": 1, "activities": [
                {"name": "A", "estimated_cost_usd": 100},
                {"name": "B", "estimated_cost_usd": 80},
                {"name": "C", "estimated_cost_usd": 60},
            ]},
            {"day": 2, "activities": [
                {"name": "D", "estimated_cost_usd": 90},
                {"name": "E", "estimated_cost_usd": 70},
            ]},
        ]
    }


def _sample_scoring_report():
    return {
        "Day 1": {"A": {"overall": 0.9}, "B": {"overall": 0.3}, "C": {"overall": 0.5}},
        "Day 2": {"D": {"overall": 0.2}, "E": {"overall": 0.8}},
    }


def test_drops_lowest_scored_first_until_under_budget():
    result = _trim_to_budget(_sample_itinerary(), _sample_scoring_report(), budget_cap=300)
    # total is 400; dropping D (0.2, -90) then B (0.3, -80) gets to 230, under 300
    assert result["itinerary"]["total_estimated_activity_cost"] == 230
    assert set(result["itinerary"]["trimmed_activities"]) == {"B", "D"}
    assert result["itinerary"]["still_over_budget"] is False


def test_never_empties_a_day_even_if_still_over_budget():
    result = _trim_to_budget(_sample_itinerary(), _sample_scoring_report(), budget_cap=50)
    remaining = {day["day"]: len(day["activities"]) for day in result["itinerary"]["days"]}
    assert all(count >= 1 for count in remaining.values())
    assert result["itinerary"]["still_over_budget"] is True


def test_scoring_report_is_filtered_to_match_remaining_activities():
    result = _trim_to_budget(_sample_itinerary(), _sample_scoring_report(), budget_cap=300)
    remaining_names = {a["name"] for day in result["itinerary"]["days"] for a in day["activities"]}
    scored_names = {name for day_scores in result["scoring_report"].values() for name in day_scores}
    assert scored_names == remaining_names


def test_no_trim_needed_when_already_under_budget():
    result = _trim_to_budget(_sample_itinerary(), _sample_scoring_report(), budget_cap=1000)
    assert result["itinerary"]["trimmed_activities"] == []
    assert result["itinerary"]["total_estimated_activity_cost"] == 400
