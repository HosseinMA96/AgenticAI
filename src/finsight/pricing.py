"""$ per token, so every eval run reports what it cost (CLAUDE.md).

USD per 1M tokens, Azure Global Standard. Looked up 2026-10-10:
- gpt-5.4-nano: Azure rates via azurespeed.com / cloudprice.net (match each other).
- gpt-5.4: no Azure-specific source found. OpenAI direct-API list price used; cached = 10% of
  input is an ASSUMPTION. Check the Azure pricing page before trusting $ to the cent.
"""

PRICES = {  # model: (input, cached_input, output)
    "gpt-5.4": (2.50, 0.25, 15.00),
    "gpt-5.4-nano": (0.20, 0.02, 1.25),
}


def cost_usd(model: str, usage: dict) -> float:
    """usage: MAF usage_details. Cached tokens are part of input_token_count, billed cheaper."""
    p_in, p_cached, p_out = PRICES[model]
    cached = usage.get("cache_read_input_token_count") or 0
    fresh = (usage.get("input_token_count") or 0) - cached
    out = usage.get("output_token_count") or 0  # includes reasoning tokens
    return (fresh * p_in + cached * p_cached + out * p_out) / 1_000_000
