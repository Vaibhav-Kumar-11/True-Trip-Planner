# The True Trip Planner

A multi-agent travel itinerary planner built with LangGraph. Capstone project for the
Analytics Club's Agentic AI bootcamp (Learners' Space 2026).

[Architecture diagram](docs/architecture.svg)

## The problem

Most "itinerary help" comes from sources with a hidden incentive: travel agents and
blogs often have commission tie-ups with the places they recommend, and popular
itineraries route everyone through the same overcrowded spots while missing what
locals actually recommend. There's no easy way to cross-check a mainstream
recommendation against genuine local opinion, or to see whether a suggested plan
actually fits your budget and group.

This project cross-references mainstream travel sources against real local insight
(Reddit/Quora), scores every activity across multiple dimensions instead of trusting
a single source, and asks the user directly when a decision genuinely can't be
automated (e.g. a budget trade-off).

## Architecture

5 specialist agents coordinated via a **Parallel + Aggregator** orchestration pattern
(full diagram: [docs/architecture.svg](docs/architecture.svg)):

```
                 ┌──────────────┐
        ┌───────▶│   Research   │───────┐
        │        └──────────────┘       │
        │        ┌──────────────┐       │
        │───────▶│ Local Insight│───────│
 START ─┤        └──────────────┘       ├──▶ Aggregator ──▶ (human review if
        │        ┌──────────────┐       │      (scoring)      over budget) ──▶ Final
        │───────▶│    Budget    │───────│                                     Itinerary
        │        └──────────────┘       │
        │        ┌──────────────┐       │
        └───────▶│    Flight    │───────┘
                 └──────────────┘
```

- **Research Agent** — searches for mainstream/popular things to do at the destination
- **Local-Insight Agent** — searches Reddit/Quora/blogs specifically for hidden gems,
  overrated spots, and safety notes; this is the core differentiator versus a generic
  "AI trip planner"
- **Budget Agent** — deterministic per-category budget split (stay/food/transport/activities)
  scaled to traveler count
- **Flight-Estimate Agent** — searches for an approximate flight price range for the
  given dates and traveler count (not a live booking integration)
- **Aggregator Agent** — merges all 4 outputs into a day-by-day plan and scores every
  activity across 4 dimensions before finalizing

### The 4-dimension scoring engine

Every candidate activity is scored, not just accepted from the LLM's first draft.
Each dimension is a continuous 0-1 value (not a binary flag) so scores genuinely vary
per activity instead of clustering on 2-3 repeated numbers:

| Dimension | What it measures |
|---|---|
| Budget-fit | Continuous: how much of the remaining per-day activity budget this activity consumes. |
| Authenticity | Continuous 0-1 score from the LLM itself (grounded in the local-insight vs. mainstream research context) — not a hardcoded hidden-gem/mainstream flag. |
| Interest-fit | Does it match the traveler's chosen interest tags (scenic/culture/shopping/nightlife)? |
| Logistics feasibility | Combines time-of-day (late-night activities score lower, more so with kids in the group) and daily pacing (an overpacked day is marked less feasible). |

`overall` is the average of the 4. Because 3 of the 4 inputs are continuous and
data-driven, scores spread naturally across activities instead of landing on the same
value every time.

### State management

All 5 agents share one `TripPlanState` object, but each of the 4 parallel agents only
ever writes to its own dedicated key (`research_findings`, `local_insights`,
`budget_breakdown`, `flight_estimate`). That's what makes it safe for them to run
concurrently with no risk of overwriting each other's work.

### Failure handling (3 mechanisms)

1. **Retries** — if an LLM call doesn't return valid JSON, it's retried once with a
   stricter prompt before giving up (`tools/llm.py::invoke_json`).
2. **Fallback** — if the Local-Insight agent's niche Reddit/Quora query returns nothing,
   it broadens to a general destination query rather than failing outright (implemented
   as a broader search, not a dependency on another agent's live output, since Research
   and Local-Insight run in parallel and can't rely on each other's state mid-flight).
3. **Human-in-the-loop** — reserved for exactly one genuinely ambiguous decision: if the
   drafted itinerary exceeds the activities budget by more than 15%, the graph pauses
   (LangGraph `interrupt()`) and asks the user to cut activities, raise the budget, or
   proceed anyway. Routine agent-level failures are handled automatically (1 and 2);
   a human is only asked when there's no objectively correct answer.

Additionally, `tools/llm.py` retries on Groq 429 (rate-limit) errors with a backoff
delay before giving up — a real failure mode hit repeatedly during testing (see below),
separate from the 3 mechanisms above which handle bad/missing agent output rather than
provider-level throttling.

## Tech stack

- **LangGraph** — multi-agent orchestration, state management, human-in-the-loop interrupts
- **Groq** (Llama 3.3 70B) — LLM inference
- **Tavily** — web search API for all 3 search-based agents
- **Streamlit** — dashboard UI

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Create a `.env` file (see `.env.example`) with:

```
GROQ_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here
```

Run the dashboard:

```bash
streamlit run app.py
```

## Validation

`validate.py` runs the full pipeline end-to-end across 10 configurations spanning 5
destinations (Bali, Goa, Bangkok, Kyoto, Rome) and varied traveler compositions (solo,
couple + 1 kid, family of 4) to confirm the system generalizes rather than being
hardcoded around a single demo case:

```bash
python validate.py
```

8/10 passed cleanly against the live Groq + Tavily APIs; the remaining 2 (Rome) hit
Groq's free-tier **daily** token quota after extensive same-day testing — a real
constraint of the free tier, not an application bug (the per-minute rate-limit
mechanism above handles the more common case; a daily cap needs a fresh day or a
second key, not a backoff).

## Notable issues found & fixed during development

- **Streamlit was parsing dollar amounts as LaTeX.** The human-review message
  (`"...($370)..."`) rendered as broken italic math because Streamlit's markdown
  renderer treats `$...$` as an inline formula. Fixed by escaping literal `$` before
  passing budget-overrun messages to `st.warning`.
- **Scoring looked hardcoded.** The original authenticity/logistics scores were binary
  flags (e.g. `0.9` or `0.5` only), so the same 2-3 `overall` values kept repeating
  across activities. Replaced with continuous, data-driven formulas (see the scoring
  engine section above) so scores now vary genuinely per activity.

## Future scope

Not built in this version, but designed for: live flight-booking API integration,
credit-card/cashback offer matching, and cross-platform price comparison for
accommodations. Cut for time; the core multi-agent orchestration was the priority.
