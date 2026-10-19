"""Typed messages that travel along the workflow's edges (D34).

Each one carries everything the next node needs, so no node reads another agent's conversation.
"""

from typing import Literal

from pydantic import BaseModel, Field

from finsight.models import Answer, Route, Verdict


class Step(BaseModel):
    """One agent call, for cost and debugging. Every message carries the steps so far, so the
    Report ends with a per-agent breakdown, and no node needs to read another's conversation."""
    agent: str
    model: str
    usage: dict = Field(default_factory=dict)  # MAF usage_details
    tools_used: list[str] = Field(default_factory=list)
    limit_hit: bool = False  # D5
    unread_citations: list[int] = Field(default_factory=list)  # D30


class Question(BaseModel):
    """The workflow's input."""
    doc_name: str
    question: str


class Routed(BaseModel):
    question: Question
    route: Route
    steps: list[Step] = Field(default_factory=list)


class Draft(BaseModel):
    """One Research attempt. attempt counts from 1; a failed check allows one retry (D31)."""
    routed: Routed
    answer: Answer
    attempt: int
    steps: list[Step] = Field(default_factory=list)


class Checked(BaseModel):
    """The Verifier's result. A failed first attempt goes back to Research, carrying verdict.problem."""
    draft: Draft
    verdict: Verdict
    steps: list[Step] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    """What the human sees: the answer that failed verification twice, and why."""
    checked: Checked


class ReviewDecision(BaseModel):
    approved: bool
    note: str = ""


class Report(BaseModel):
    """The workflow's output, one per question."""
    question: Question
    status: Literal["verified", "human_approved", "human_rejected", "oos"]
    route: Route
    answer: Answer | None = None  # None when oos: no research ran
    verdict: Verdict | None = None
    attempts: int = 0
    reviewer_note: str = ""
    steps: list[Step] = Field(default_factory=list)
