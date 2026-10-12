"""FinSight's tunable settings, in one place (D6).

Plain constants on purpose: every change shows up as a diff that can be tied
to an eval result. Secrets never go here; they stay in the root .env.
"""

# Deployments on atlas-foundry-hma96. Two tiers so we can later measure
# cost vs quality per role (week 4).
MAIN_MODEL = "gpt-5.4"  # reasoning + vision
CHEAP_MODEL = "gpt-5.4-nano"  # routing, extraction

# Tool-loop limits per agent.run() (D5). Starting guesses; tune with evals.
MAX_ITERATIONS = 10  # model round-trips (one can request several tools)
MAX_FUNCTION_CALLS = 20  # total tool runs
MAX_DURATION_SECONDS = 60.0  # wall-clock budget for the tool loop

# search_filings (D24, D25). Mode is measured on the agent, not picked from the
# retrieval eval, because the agent writes cleaner queries than the raw questions.
SEARCH_MODE = "vector"  # or "hybrid+rerank", "hybrid", "keyword"; try others with evals.run --search-mode
SEARCH_TOP = 3  # pages per call, same as the week-1 keyword tool
