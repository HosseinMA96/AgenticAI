"""
Enhanced Workflow Orchestration Example

Demonstrates the new fluent API for building workflows with
improved readability and reduced boilerplate.
"""

import asyncio

from pydantic import BaseModel

from picoagents.workflow import FunctionStep, Workflow, WorkflowRunner
from picoagents.workflow.core import Context, StepMetadata, WorkflowMetadata


# Define data types
class NumberInput(BaseModel):
    value: int


class NumberOutput(BaseModel):
    result: int


class StringInput(BaseModel):
    text: str


class StringOutput(BaseModel):
    text: str


# Define step functions
async def double_number(input_data: NumberInput, context: Context) -> NumberOutput:
    """Double the input value."""
    result = input_data.value * 2
    print(f"🔢 Double: {input_data.value} → {result}")
    return NumberOutput(result=result)


async def add_ten(input_data: NumberOutput, context: Context) -> NumberOutput:
    """Add 10 to the input value."""
    result = input_data.result + 10
    print(f"➕ Add Ten: {input_data.result} → {result}")
    return NumberOutput(result=result)


async def square_number(input_data: NumberOutput, context: Context) -> NumberOutput:
    """Square the input value."""
    result = input_data.result**2
    print(f"📐 Square: {input_data.result} → {result}")
    return NumberOutput(result=result)


async def format_result(input_data: NumberOutput, context: Context) -> StringOutput:
    """Format the final number as a string."""
    text = f"Final result: {input_data.result}"
    print(f"📝 Format: {input_data.result} → '{text}'")
    return StringOutput(text=text)


def get_workflow():
    """Create a general workflow pipeline."""
    # Create reusable steps
    double_step = FunctionStep(
        step_id="double",
        metadata=StepMetadata(name="Double Number"),
        input_type=NumberInput,
        output_type=NumberOutput,
        func=double_number,
    )

    add_ten_step = FunctionStep(
        step_id="add_ten",
        metadata=StepMetadata(name="Add Ten"),
        input_type=NumberOutput,
        output_type=NumberOutput,
        func=add_ten,
    )

    square_step = FunctionStep(
        step_id="square",
        metadata=StepMetadata(name="Square Number"),
        input_type=NumberOutput,
        output_type=NumberOutput,
        func=square_number,
    )

    format_step = FunctionStep(
        step_id="format",
        metadata=StepMetadata(name="Format Result"),
        input_type=NumberOutput,
        output_type=StringOutput,
        func=format_result,
    )

    # Create extended pipeline workflow
    workflow = Workflow(metadata=WorkflowMetadata(name="General Pipeline")).chain(
        double_step, square_step, add_ten_step, format_step
    )

    return workflow


workflow = get_workflow()


async def main():
    """Demonstrate different workflow construction patterns."""

    print("=== Enhanced Workflow Orchestration Examples ===\n")
    print("Running workflow: input → double → square → add_ten → format\n")

    runner = WorkflowRunner()
    result = await runner.run(workflow, {"value": 3})
    print(f"\nFinal: {result.step_executions['format'].output_data}")

    print("\n" + "=" * 50)
    print("✨ Fluent API Benefits:")
    print("• 🎯 Concise: Single line workflow construction")
    print("• 🔒 Type-safe: Direct step references prevent typos")
    print("• 🤖 Auto-registration: Steps added automatically")
    print("• 📖 Readable: Flows naturally left-to-right")
    print("• ⚡ Efficient: Minimal boilerplate code")


if __name__ == "__main__":
    asyncio.run(main())
