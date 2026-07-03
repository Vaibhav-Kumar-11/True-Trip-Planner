"""Runs the planner end-to-end across 6 configurations (3 destinations x solo/family)
to confirm the system generalizes rather than being hardcoded to one demo case."""

from dotenv import load_dotenv
load_dotenv()

from langgraph.types import Command
from graph import build_graph

CONFIGS = [
    ("Bali", "scenic", 2, 0, 1500),
    ("Bali", "scenic", 2, 2, 2500),
    ("Goa", "nightlife", 2, 1, 1600),
    ("Goa", "scenic", 1, 0, 900),
    ("Bangkok", "shopping", 2, 0, 1200),
    ("Bangkok", "nightlife", 2, 2, 2200),
    ("Kyoto", "culture", 2, 0, 1800),
    ("Kyoto", "culture", 2, 1, 2200),
    ("Rome", "culture", 2, 0, 2000),
    ("Rome", "shopping", 2, 2, 3200),
]


def run_config(graph, destination, tag, adults, kids, budget):
    config = {"configurable": {"thread_id": f"validate-{destination}-{adults}-{kids}"}}
    initial_state = {
        "destination": destination,
        "start_date": "2026-08-10",
        "end_date": "2026-08-15",
        "num_days": 5,
        "adults": adults,
        "kids": kids,
        "total_budget": float(budget),
        "interest_tags": [tag],
    }
    result = graph.invoke(initial_state, config=config)
    if "__interrupt__" in result:
        result = graph.invoke(Command(resume="cut_activities"), config=config)
    return result


def main():
    graph = build_graph()
    passed = 0

    for destination, tag, adults, kids, budget in CONFIGS:
        label = f"{destination} | adults={adults} kids={kids} budget=${budget}"
        print(f"\n=== {label} ===")
        try:
            result = run_config(graph, destination, tag, adults, kids, budget)
            final = result.get("final_itinerary", {})
            days = len(final.get("days", []))
            activities = sum(len(d.get("activities", [])) for d in final.get("days", []))
            print(f"OK: {days} days, {activities} activities, cost=${final.get('total_estimated_activity_cost')}")
            passed += 1
        except Exception as e:
            print(f"FAILED: {e}")

    print(f"\n{passed}/{len(CONFIGS)} configurations passed")


if __name__ == "__main__":
    main()
