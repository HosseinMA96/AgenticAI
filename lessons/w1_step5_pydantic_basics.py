"""Week 1, Step 5 — Pydantic basics (lesson only, no LLM).

A model describes the shape we expect; validation either gives us a typed
object or a ValidationError that says exactly what was wrong.
"""

from pydantic import BaseModel, ValidationError


class Answer(BaseModel):
    value: float
    unit: str
    citations: list[int]  # page numbers


# 1. Good data -> typed object.
good = Answer.model_validate({"value": 12.5, "unit": "USD bn", "citations": [41, 42]})
print("good:     ", good)

# 2. "Close enough" data -> Pydantic coerces it (string "12.5" becomes float 12.5).
#    Worth knowing: LLMs often send numbers as strings.
loose = Answer.model_validate({"value": "12.5", "unit": "USD bn", "citations": ["41"]})
print("coerced:  ", loose)

# 3. Bad data -> ValidationError listing every problem at once.
try:
    Answer.model_validate({"value": "about twelve", "citations": [41]})
except ValidationError as e:
    print("\nbad ->", e)
