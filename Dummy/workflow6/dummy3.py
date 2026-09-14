"""
Conditional Branching Workflow Example

Demonstrates conditional routing based on step output:

    Input (number to classify)
           ↓
       [classify]  ← Classifies as "high" or "low"
           ↓
    ┌─────┴─────┐
    ↓           ↓
 category    category
 == "high"  == "low"
    ↓           ↓
[process_   [process_
  high]       low]
    ↓           ↓
  Output      Output

Patterns demonstrated:
1. Fan-out with output_based conditions (one step → two conditional paths)
2. Equality operator (==) for mutually exclusive routing
3. Multiple end steps (workflow completes when any end step finishes)

Run: python examples/workflows/conditional.py
"""

import asyncio

from pydantic import BaseModel

from picoagents.workflow import FunctionStep, Workflow, WorkflowRunner
from picoagents.workflow.core import Context, StepMetadata, WorkflowMetadata


# =============================================================================
# Data Models
# =============================================================================


class NumberInput(BaseModel):
    """Input: a number to classify."""

    value: int


class ClassifyOutput(BaseModel):
    """Output from classification: the category and original value."""

    category: str  # "high" or "low"
    value: int


class ProcessedOutput(BaseModel):
    """Final processed output."""

    result: str
    original_value: int
    multiplier: int


# =============================================================================
# Step Functions
# =============================================================================


async def classify_number(
    input_data: NumberInput, context: Context
) -> ClassifyOutput:
    """Classify number as high (>= 50) or low (< 50)."""
    print(f"\n📊 [classify] Classifying number: {input_data.value}")
    await asyncio.sleep(0.3)

    category = "high" if input_data.value >= 50 else "low"

    print(f"   Value {input_data.value} → Category: '{category}'")
    print(f"   Routing to the '{category}' processing branch...")

    return ClassifyOutput(category=category, value=input_data.value)


async def process_high(
    input_data: ClassifyOutput, context: Context
) -> ProcessedOutput:
    """Process high-value numbers (multiply by 10)."""
    print(f"\n🔥 [process_high] Processing HIGH value: {input_data.value}")
    await asyncio.sleep(0.3)

    multiplier = 10
    result = input_data.value * multiplier

    print(f"   Applied multiplier: x{multiplier}")
    print(f"   Result: {input_data.value} × {multiplier} = {result}")

    return ProcessedOutput(
        result=f"High value processed: {result}",
        original_value=input_data.value,
        multiplier=multiplier,
    )


async def process_low(
    input_data: ClassifyOutput, context: Context
) -> ProcessedOutput:
    """Process low-value numbers (multiply by 2)."""
    print(f"\n❄️ [process_low] Processing LOW value: {input_data.value}")
    await asyncio.sleep(0.3)

    multiplier = 2
    result = input_data.value * multiplier

    print(f"   Applied multiplier: x{multiplier}")
    print(f"   Result: {input_data.value} × {multiplier} = {result}")

    return ProcessedOutput(
        result=f"Low value processed: {result}",
        original_value=input_data.value,
        multiplier=multiplier,
    )


# =============================================================================
# Workflow Construction
# =============================================================================


def get_workflow() -> Workflow:
    """
    Build a conditional branching workflow.

    Edge conditions use output_based routing on category field:
    - classify → process_high: when category == "high" (value >= 50)
    - classify → process_low:  when category == "low"  (value < 50)

    Both branches are end steps, so the workflow completes when
    either branch finishes (only one will execute per run).
    """
    # Create steps
    classify_step = FunctionStep(
        step_id="classify",
        metadata=StepMetadata(name="Classify Number"),
        input_type=NumberInput,
        output_type=ClassifyOutput,
        func=classify_number,
    )

    process_high_step = FunctionStep(
        step_id="process_high",
        metadata=StepMetadata(name="Process High Value"),
        input_type=ClassifyOutput,
        output_type=ProcessedOutput,
        func=process_high,
    )

    process_low_step = FunctionStep(
        step_id="process_low",
        metadata=StepMetadata(name="Process Low Value"),
        input_type=ClassifyOutput,
        output_type=ProcessedOutput,
        func=process_low,
    )

    # Build workflow
    workflow = Workflow(
        metadata=WorkflowMetadata(
            name="Conditional Branching Workflow",
            description="Routes to different processors based on input value",
        )
    )

    # Add all steps
    workflow.add_step(classify_step)
    workflow.add_step(process_high_step)
    workflow.add_step(process_low_step)

    # Fan-out: classify → two conditional branches (mutually exclusive)
    workflow.add_edge(
        "classify",
        "process_high",
        {"type": "output_based", "field": "category", "operator": "==", "value": "high"},
    )
    workflow.add_edge(
        "classify",
        "process_low",
        {"type": "output_based", "field": "category", "operator": "==", "value": "low"},
    )

    # Set start and BOTH branches as end steps
    workflow.set_start_step("classify")
    workflow.add_end_step("process_high")
    workflow.add_end_step("process_low")

    return workflow


# Create workflow instance for import
workflow = get_workflow()


# =============================================================================
# Main: Run Examples
# =============================================================================


async def run_example(value: int, description: str):
    """Run workflow with a specific input value."""
    print("\n" + "=" * 60)
    print(f"TEST: {description}")
    print(f"Input value: {value}")
    print("=" * 60)

    runner = WorkflowRunner()
    input_data = {"value": value}

    result = await runner.run(workflow, input_data)

    # Find the completed end step
    for step_id in workflow.end_step_ids:
        step_exec = result.step_executions.get(step_id)
        if step_exec and step_exec.output_data:
            print(f"\n✨ FINAL RESULT:")
            print(f"   {step_exec.output_data.get('result', 'N/A')}")
            break


async def main():
    """Demonstrate conditional branching with different input values."""

    print("=" * 60)
    print("CONDITIONAL BRANCHING WORKFLOW EXAMPLE")
    print("=" * 60)
    print("""
The classify step routes to process_high (x10 multiplier) when input >= 50,
or process_low (x2 multiplier) when input < 50. Only one branch executes.
    """)

    # Test Case 1: High value (>= 50)
    await run_example(75, "High value (>= 50) → process_high branch")

    # Test Case 2: Low value (< 50)
    await run_example(25, "Low value (< 50) → process_low branch")

    # Test Case 3: Boundary case
    await run_example(50, "Boundary case (exactly 50) → process_high branch")

    print("\n" + "=" * 60)
    print("All test cases completed!")
    print("Notice how each input value took a different conditional branch.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
