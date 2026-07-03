import uuid

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from langgraph.types import Command
from graph import build_graph

st.set_page_config(page_title="The True Trip Planner", layout="wide")
st.title("The True Trip Planner")
st.caption(
    "A multi-agent itinerary planner that cross-checks mainstream travel advice against "
    "real local (Reddit/Quora) insight, instead of trusting a single biased source."
)

if "graph" not in st.session_state:
    st.session_state.graph = build_graph()
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "result" not in st.session_state:
    st.session_state.result = None

with st.form("trip_form"):
    col1, col2 = st.columns(2)
    with col1:
        destination = st.text_input("Destination", "Bali")
        start_date = st.text_input("Start date (YYYY-MM-DD)", "2026-08-10")
        end_date = st.text_input("End date (YYYY-MM-DD)", "2026-08-15")
        num_days = st.number_input("Number of days", min_value=1, max_value=30, value=5)
    with col2:
        adults = st.number_input("Adults", min_value=1, max_value=10, value=2)
        kids = st.number_input("Kids", min_value=0, max_value=10, value=0)
        total_budget = st.number_input("Total budget (USD)", min_value=50, value=1500)
        interest_tags = st.multiselect(
            "Interests", ["scenic", "culture", "shopping", "nightlife"], default=["scenic", "culture"]
        )

    submitted = st.form_submit_button("Plan my trip")

if submitted:
    st.session_state.thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    initial_state = {
        "destination": destination,
        "start_date": start_date,
        "end_date": end_date,
        "num_days": int(num_days),
        "adults": int(adults),
        "kids": int(kids),
        "total_budget": float(total_budget),
        "interest_tags": interest_tags,
    }
    with st.spinner("Dispatching 4 specialist agents (research, local-insight, budget, flight)..."):
        result = st.session_state.graph.invoke(initial_state, config=config)
    st.session_state.result = result

result = st.session_state.result

if result and "__interrupt__" in result:
    payload = result["__interrupt__"][0].value
    # Streamlit's markdown renderer treats "$...$" as LaTeX - escape literal dollar signs
    # so budget amounts don't get parsed as math.
    escaped_reason = (payload["reason"] or "").replace("$", "\\$")
    st.warning(f"Human review needed: {escaped_reason}")
    choice = st.radio(
        "What would you like to do?",
        ["cut_activities", "increase_budget", "proceed_anyway"],
        format_func=lambda c: {
            "cut_activities": "Cut the lowest-scored activities to fit the budget",
            "increase_budget": "Keep the plan, I'll increase my budget",
            "proceed_anyway": "Proceed anyway, I'm OK going over budget",
        }[c],
    )
    if st.button("Confirm decision"):
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        st.session_state.result = st.session_state.graph.invoke(Command(resume=choice), config=config)
        st.rerun()

elif result and result.get("final_itinerary"):
    itinerary = result["final_itinerary"]

    st.subheader(f"Your {destination} itinerary")
    m1, m2, m3 = st.columns(3)
    m1.metric("Estimated activity cost", f"${itinerary.get('total_estimated_activity_cost', 0):.0f}")
    m2.metric("Total budget", f"${result.get('budget_breakdown', {}).get('activities', 0):.0f} (activities)")
    m3.metric("Travelers", f"{adults} adult(s), {kids} kid(s)")

    if itinerary.get("trimmed_activities"):
        st.info(f"Trimmed to fit budget: {', '.join(itinerary['trimmed_activities'])}")

    scoring_report = result.get("scoring_report", {})

    for day in itinerary.get("days", []):
        day_key = f"Day {day['day']}"
        st.markdown(f"### {day_key}")
        for act in day.get("activities", []):
            tag = "Hidden gem" if act.get("is_hidden_gem") else "Mainstream"
            st.write(
                f"**{act['name']}** ({act.get('category')}, {act.get('time_of_day')}) "
                f"— ${act.get('estimated_cost_usd', 0)} — {tag}"
            )
            st.caption(act.get("description", ""))

        day_scores = scoring_report.get(day_key)
        if day_scores:
            scores_df = pd.DataFrame.from_dict(day_scores, orient="index")
            scores_df.index.name = "Activity"
            st.table(scores_df)

    st.subheader("Budget breakdown")
    budget_df = pd.DataFrame(
        list(result.get("budget_breakdown", {}).items()), columns=["Category", "Amount (USD)"]
    ).set_index("Category")
    st.table(budget_df)

    st.subheader("Flight estimate")
    flight = result.get("flight_estimate", {})
    flight_df = pd.DataFrame(
        [
            ["Price range per traveler (USD)", flight.get("price_range_usd", "unknown")],
            ["Common routes", ", ".join(flight.get("common_routes", [])) or "N/A"],
        ],
        columns=["Field", "Value"],
    ).set_index("Field")
    st.table(flight_df)
    st.caption(flight.get("summary", ""))

    with st.expander("Raw agent findings (research & local-insight)"):
        st.write("**Research agent:**", result.get("research_findings", {}).get("summary", "N/A"))
        st.write("**Local-insight agent:**", result.get("local_insights", {}).get("summary", "N/A"))
