# The True Trip Planner

A multi-agent travel itinerary planner built with LangGraph, for the Analytics Club's
Agentic AI bootcamp (Learners' Space 2026) capstone project.

## Problem

Travel-agent itineraries and popular blog posts often come with a hidden incentive —
commission tie-ups with the places they recommend — and they tend to route everyone
through the same overcrowded spots while skipping what locals actually recommend.
There is no easy way to check a mainstream recommendation against genuine local
opinion, or to see whether a suggested plan actually fits a given budget and group.

This project cross-references mainstream travel sources against real local insight
(Reddit/Quora), scores every candidate activity across four dimensions instead of
trusting a single source, and asks the user directly only when a decision genuinely
cannot be automated (a budget trade-off).

## Architecture

![Architecture diagram](docs/architecture.svg)

Five specialist agents, coordinated through a **Parallel + Aggregator** orchestration
pattern:

| Agent | Responsibility |
|---|---|
| Research | Mainstream/popular things to do at the destination (Tavily search) |
| Local-Insight | Reddit/Quora/blog search for hidden gems, overrated spots, and safety notes — the core differentiator from a generic "AI trip planner" |
| Budget | Deterministic per-category budget split (stay/food/transport/activities), scaled to traveler count |
| Flight-Estimate | Approximate flight price range for the given dates and traveler count (a search-based estimate, not a live booking integration) |
| Aggregator | Merges the four outputs into a day-by-day plan and scores every activity before finalizing |

**State management.** All five agents share one `TripPlanState` object, but Research,
Local-Insight, Budget, and Flight each write only to their own dedicated key. That is
what makes it safe for them to run concurrently with no risk of overwriting each
other's work — deliberate, not incidental.

**Why Parallel + Aggregator.** Research, Local-Insight, Budget, and Flight are
independent lookups — none of them needs another's output to do its job — so they fan
out concurrently and a single Aggregator node merges the results and resolves
conflicts (like a budget overrun). Local-Insight's own fallback (below) is
self-contained rather than reading Research's output, precisely because the two run
in parallel and cannot depend on each other mid-flight.

### The 4-dimension scoring engine

Every candidate activity is scored before the itinerary is finalized, rather than
being accepted as-is from the LLM's first draft. Each dimension is a continuous 0-1
value, not a binary flag, so scores vary meaningfully instead of clustering on a
handful of repeated numbers:

| Dimension | What it measures |
|---|---|
| Budget-fit | How much of the remaining per-day activity budget this activity consumes |
| Authenticity | A continuous 0-1 score from the LLM itself, grounded in the local-insight vs. mainstream research context — not a hardcoded hidden-gem/mainstream flag |
| Interest-fit | Whether the activity matches the traveler's chosen interest tags (scenic/culture/shopping/nightlife) |
| Logistics feasibility | Time-of-day (late-night activities score lower, more so with kids in the group) combined with daily pacing (an overpacked day is marked less feasible) |

`overall` is the average of the four. Because three of the four inputs are continuous
and data-driven, scores spread naturally across activities.

### Failure handling

1. **Retries** — if an LLM call does not return valid JSON, it is retried once with a
   stricter prompt before giving up (`tools/llm.py::invoke_json`).
2. **Fallback** — if Local-Insight's niche Reddit/Quora query returns nothing, it
   broadens to a general destination query rather than failing outright.
3. **Human-in-the-loop** — reserved for exactly one genuinely ambiguous decision: if
   the drafted itinerary exceeds the activities budget by more than 15%, the graph
   pauses (LangGraph `interrupt()`) and asks the user to cut activities, raise the
   budget, or proceed anyway. If "cut activities" is chosen, the lowest-scored
   activities are dropped one at a time until the plan fits the budget (or every day
   is down to one activity, whichever comes first).
4. **Rate-limit backoff** — Groq's free tier throttles on tokens-per-minute; a 429 is
   retried with a short backoff delay rather than failing the whole run.

Mechanisms 1, 2, and 4 are fully automatic — no human involved, because there is an
objectively correct recovery. Mechanism 3 is used deliberately, and only once, because
a budget trade-off has no single correct answer; that is a decision for the user, not
the system.

## Tech stack

- **LangGraph** — multi-agent orchestration, shared state, human-in-the-loop interrupts
- **Groq** (Llama 3.3 70B) — LLM inference
- **Tavily** — web search API for the three search-based agents
- **Streamlit** — dashboard UI
- **Python**

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

`validate.py` runs the full pipeline end-to-end across 12 configurations — 4
destinations (Bali, Goa, Bangkok, Kyoto) x 3 traveler compositions (solo, couple with
one child, family of four) — to confirm the system generalizes rather than being
hardcoded around a single demo case:

```bash
python validate.py
```

## Known limitations and what it would take to fix them

These were deliberately left out of scope for this submission. Each row is something
that could reasonably be asked about in review — the third column is the honest
answer.

| Dropped | Why | What implementing it would take |
|---|---|---|
| Live flight booking | Real GDS/flight APIs (Amadeus, Skyscanner) need paid access and complex auth; out of scope for a one-week build | Integrate the Amadeus Self-Service API, add a booking-confirmation step, and extend the state schema with a `flight_booking` slot |
| Credit-card/cashback offer matching | No reliable free data source for card-specific offers | Would need a partnership-style data feed (e.g. CardPointers-like API) or manual curation per issuer; not something a search API can answer |
| Cross-platform price comparison | Different product from itinerary planning; would need its own scraping/comparison infrastructure | A separate agent that queries multiple booking sites for the same stay/activity and normalizes prices for comparison |
| Live deployment | Not required for grading; optional polish | Deploy via Streamlit Community Cloud (free), pointing at this repo with `GROQ_API_KEY`/`TAVILY_API_KEY` set as secrets |

## Issues found and fixed during development

- **Streamlit was rendering dollar amounts as LaTeX.** Its markdown renderer treats
  `$...$` as an inline math span, so any free-form text with two or more `$` in it
  (a budget-overrun message, a flight-price summary) rendered as broken italic math.
  Fixed by escaping literal `$` before passing any LLM-generated text to
  `st.write`/`st.caption`/`st.warning`/`st.info`.
- **Scoring looked hardcoded.** The original authenticity and logistics-feasibility
  scores were binary flags (two possible values each), so `overall` kept landing on
  the same 2-3 numbers across different activities. Replaced both with continuous,
  data-driven formulas so scores now vary genuinely per activity.
- **Budget trimming didn't actually respect the budget.** The "cut activities" path
  originally dropped a fixed ~20% of activities regardless of how far over budget the
  plan was, so a large overrun could still leave the trimmed plan well over budget.
  Fixed to drop the lowest-scored activities one at a time until the plan fits (or
  every day is down to one activity).
