"""Typed messages that cross agent boundaries.

Field descriptions are part of the prompt: they are all the model sees of
this class (lesson w1_step7). Validators are the checks the model can't
talk its way past (lesson w1_step8).
"""

from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, model_validator


class Answer(BaseModel):
    # Field order is generation order, so reasoning comes first: the model
    # works it out before it commits to a number.
    reasoning: str = Field(
        description="Short explanation of how the value was found or calculated from the evidence."
    )
    # None is a legal answer. Without it the model invents a number (lesson w1_step8).
    value: float | None = Field(
        description="The answer as a plain number, for the exact company and period asked. "
        "null if the evidence does not state it or allow calculating it."
    )
    unit: str | None = Field(
        description="Unit of value, e.g. 'USD millions', 'percent', 'ratio'. null if value is null."
    )
    citations: list[int] = Field(
        description="Page numbers whose text states the value or the inputs used to calculate it. "
        "Empty if value is null."
    )
    # Three named levels, not a float (D7). The Verifier gets the final say in week 3.
    confidence: Literal["high", "medium", "low"] = Field(
        description="high: value stated directly on a cited page. "
        "medium: calculated from stated numbers, or wording is ambiguous. "
        "low: evidence is partial or indirect."
    )

    @model_validator(mode="after")
    def check_consistency(self, info: ValidationInfo) -> "Answer":
        if self.value is not None and not self.citations:
            raise ValueError("a value needs at least one citation")
        if self.value is None and self.citations:
            raise ValueError("no value, so there should be no citations")
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
