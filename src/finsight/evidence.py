"""Which pages did the agent actually read in this run? (D30, defence B)

Poisoned memory made the agent cite p77 without ever reading it (lesson w2_step6).
Code can check that: a citation is only valid if a tool returned that page this run.
"""

import json
import re

from agent_framework import AgentResponse

_PAGE = re.compile(r"\[page (\d+)\]")  # how search_filings labels each page it returns


def _text(result) -> str:
    # Text mode returns a str; image mode a list of Content ("[page N]" text + PNG).
    if isinstance(result, list):
        return "\n".join(getattr(c, "text", None) or "" for c in result)
    return str(result or "")


def retrieved_pages(response: AgentResponse) -> set[int]:
    pages: set[int] = set()
    for m in response.messages:
        for c in m.contents:
            if c.type == "function_result":
                pages |= {int(p) for p in _PAGE.findall(_text(c.result))}
            elif c.type == "function_call" and c.name == "render_page":
                args = json.loads(c.arguments) if isinstance(c.arguments, str) else c.arguments
                pages.add(int(args["page"]))
    return pages


def unread_citations(cited: list[int], response: AgentResponse) -> list[int]:
    """Cited pages that no tool returned in this run. Empty = every citation was read."""
    return sorted(set(cited) - retrieved_pages(response))
