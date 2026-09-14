"""Control definitions evaluated against a service's ArtifactSet.

Kept minimal per TODO Phase 1 — prompt wording is not tuned here (that's an
explicit non-goal per the brief §7); these exist to give evaluate_control
something concrete to point at.
"""

from src.models import ControlSpec

CONTROLS: tuple[ControlSpec, ...] = (
    ControlSpec(
        control_id="rto_documented",
        description="Recovery Time Objective is explicitly documented for the service.",
        evaluation_prompt=(
            "Given the runbook markdown, determine whether a Recovery Time "
            "Objective (RTO) is explicitly stated. PASS if a concrete RTO "
            "value with units is present; FAIL if absent; NEEDS_REVIEW if "
            "mentioned but ambiguous or contradictory."
        ),
    ),
    ControlSpec(
        control_id="rollback_path",
        description="A documented rollback procedure exists for a failed failover.",
        evaluation_prompt=(
            "Given the runbook markdown, determine whether a rollback "
            "procedure is documented for reverting a failed failover. PASS "
            "if clear steps exist; FAIL if no rollback section exists; "
            "NEEDS_REVIEW if present but incomplete or unclear."
        ),
    ),
    ControlSpec(
        control_id="failover_test_recent",
        description="The most recent failover test occurred within the required window.",
        evaluation_prompt=(
            "Given the failover test log, determine whether the most recent "
            "successful test occurred within the last 12 months. PASS if "
            "within window; FAIL if overdue or no successful test found; "
            "NEEDS_REVIEW if the log is ambiguous about outcome or date."
        ),
    ),
    ControlSpec(
        control_id="contacts_current",
        description="The on-call/escalation contact tree in the config is current.",
        evaluation_prompt=(
            "Given the config export, determine whether the escalation "
            "contact list looks current and complete (named owners, no "
            "placeholder values). PASS if complete; FAIL if placeholders or "
            "empty entries are present; NEEDS_REVIEW if partially filled."
        ),
    ),
)
