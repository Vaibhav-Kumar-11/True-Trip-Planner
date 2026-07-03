"""Runs the planner end-to-end across a 4 destinations x 3 traveler-composition grid
(12 configurations total) to confirm the system generalizes rather than being
hardcoded to one demo case."""

from dotenv import load_dotenv
load_dotenv()

from langgraph.types import Command
from graph import build_graph

DESTINATIONS = {
    # destination: (interest tag, [budget for solo, couple+1 kid, family of 4])
    "Bali": ("scenic", [900, 1800, 2500]),
    "Goa": ("nightlife", [700, 1500, 2200]),
    "Bangkok": ("shopping", [800, 1600, 2200]),
    "Kyoto": ("culture", [1000, 2000, 3000]),
}
TRAVELER_COMPOSITIONS = [
    ("solo", 1, 0),
    ("couple + 1 kid", 2, 1),
    ("family of 4", 2, 2),
]


def build_configs():
    configs = []
    for destination, (tag, budgets) in DESTINATIONS.items():
        for (label, adults, kids), budget in zip(TRAVELER_COMPOSITIONS, budgets):
            configs.append((destination, tag, adults, kids, budget, label))
    return configs


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
    configs = build_configs()
    passed = 0

    for destination, tag, adults, kids, budget, comp_label in configs:
        label = f"{destination} ({comp_label}) | adults={adults} kids={kids} budget=${budget}"
        print(f"\n=== {label} ===")
        try:
            result = run_config(graph, destination, tag, adults, kids, budget)
            final = result.get("final_itinerary", {})
            days = len(final.get("days", []))
            activities = sum(len(d.get("activities", [])) for d in final.get("days", []))
            over_budget = final.get("still_over_budget", False)
            print(
                f"OK: {days} days, {activities} activities, "
                f"cost=${final.get('total_estimated_activity_cost')}, still_over_budget={over_budget}"
            )
            passed += 1
        except Exception as e:
            print(f"FAILED: {e}")

    print(f"\n{passed}/{len(configs)} configurations passed")


if __name__ == "__main__":
    main()
