"""Typed messages that cross agent boundaries.

Field descriptions are part of the prompt: they are all the model sees of
this class (lesson w1_step7). Validators are the checks the model can't
talk its way past (lesson w1_step8).
"""

from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, model_validator


class Answer(BaseModel):
    # Field order is generation order, so reasoning comes first: the model
    # works it out before it commits to an answer.
    reasoning: str = Field(
        description="Short explanation of how the answer was found or calculated from the evidence."
    )
    # An explicit "not found" beats a guess (lesson w1_step8). It's also what
    # the validator keys on: value=None alone can't tell "not found" from a written answer (D8).
    found: bool = Field(description="false if the evidence does not answer the question.")
    answer: str = Field(
        description="The direct answer in one or two sentences, as a person would say it. "
        "If found is false, say what is missing."
    )
    value: float | None = Field(
        description="If the question asks for one number: that number, for the exact company and period asked. "
        "null if the question needs a written answer, or if found is false."
    )
    unit: str | None = Field(
        description="Unit of value, e.g. 'USD millions', 'percent', 'ratio'. null if value is null."
    )
    citations: list[int] = Field(
        description="Page numbers whose text states the answer or the inputs used to calculate it. "
        "Empty if found is false."
    )
    # Three named levels, not a float (D7). The Verifier gets the final say in week 3.
    confidence: Literal["high", "medium", "low"] = Field(
        description="high: answer stated directly on a cited page. "
        "medium: calculated from stated numbers, or wording is ambiguous. "
        "low: evidence is partial or indirect."
    )

    @model_validator(mode="after")
    def check_consistency(self, info: ValidationInfo) -> "Answer":
        if self.found and not self.citations:
            raise ValueError("a found answer needs at least one citation")
        if not self.found and (self.citations or self.value is not None):
            raise ValueError("not found, so there should be no value and no citations")
        if self.value is not None and not self.unit:
            raise ValueError("a value needs a unit")
        if any(p < 1 for p in self.citations):
            raise ValueError("page numbers start at 1")
        # Only runs when the caller passes context={"pages": {...}}: the pages
        # actually given to the model. Catches invented page numbers, NOT
        # whether a real page supports the value (that's the Verifier's job).
        known = (info.context or {}).get("pages")
        if known is not None and not set(self.citations) <= set(known):
            raise ValueError(f"cites pages {sorted(set(self.citations) - set(known))} not in the evidence")
        return self
