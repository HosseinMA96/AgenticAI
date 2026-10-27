"""The decision log (D42): each review request can be answered once.

MAF refuses a second answer only on the latest checkpoint (lesson w3_step12). An older
checkpoint still holds the same pending request, so the guard lives here: one file per
request_id, created atomically. Whoever creates it first wins; everyone else is refused.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from finsight.orchestration.messages import ReviewDecision


class AlreadyDecided(Exception):
    def __init__(self, request_id: str, first: dict) -> None:
        super().__init__(f"request {request_id} was already answered at {first['at']}: "
                         f"{'approved' if first['approved'] else 'rejected'}")
        self.first = first


def record(folder: Path, request_id: str, decision: ReviewDecision) -> None:
    """Claim the request for this decision, or raise AlreadyDecided with the first one."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{request_id}.json"
    try:
        # O_EXCL: the OS creates the file only if it doesn't exist, as one step. Two reviewers
        # racing can't both pass this line, unlike "check if it exists, then write".
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise AlreadyDecided(request_id, json.loads(path.read_text())) from None
    with os.fdopen(fd, "w") as f:
        json.dump({**decision.model_dump(), "at": datetime.now(timezone.utc).isoformat()}, f)
