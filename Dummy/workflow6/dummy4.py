"""
Workflow Checkpoint Example

Demonstrates how to use workflow checkpoints for:
1. Auto-saving progress during execution
2. Resuming from checkpoint after failure
3. File-based persistence

Run: python -m examples.workflows.checkpoint_example
"""

import asyncio
from pathlib import Path
from pydantic import BaseModel

from picoagents.workflow import (
    Workflow,
    WorkflowRunner,
    WorkflowMetadata,
    StepMetadata,
    CheckpointConfig,
    FileCheckpointStore,
    FunctionStep,
)


# ============================================================================
# Data Models
# ============================================================================


class DataInput(BaseModel):
    text: str


class DataOutput(BaseModel):
    result: str


# ============================================================================
# Step Functions (Simulated expensive operations)
# ============================================================================


async def fetch_data(input_data: DataInput, context) -> DataOutput:
    """Simulate expensive data fetching (e.g., API call)."""
    print(f"📥 Fetching data: {input_data.text}")
    await asyncio.sleep(1)  # Simulate network delay
    return DataOutput(result=f"Fetched: {input_data.text}")


async def process_data(input_data: DataOutput, context) -> DataOutput:
    """Simulate expensive data processing (e.g., LLM call)."""
    print(f"⚙️  Processing data: {input_data.result}")
    await asyncio.sleep(1)  # Simulate processing time
    return DataOutput(result=f"Processed: {input_data.result}")


async def validate_data(input_data: DataOutput, context) -> DataOutput:
    """Simulate data validation."""
    print(f"✅ Validating data: {input_data.result}")
    await asyncio.sleep(1)  # Simulate validation time
    return DataOutput(result=f"Validated: {input_data.result}")


async def save_data(input_data: DataOutput, context) -> DataOutput:
    """Simulate saving to database."""
    print(f"💾 Saving data: {input_data.result}")
    await asyncio.sleep(1)  # Simulate DB write
    return DataOutput(result=f"Saved: {input_data.result}")


# ============================================================================
# Build Workflow
# ============================================================================


def build_workflow() -> Workflow:
    """Build a data processing workflow with 4 expensive steps."""

    fetch_step = FunctionStep(
        step_id="fetch",
        metadata=StepMetadata(name="Fetch Data", description="Fetch from API"),
        input_type=DataInput,
        output_type=DataOutput,
        func=fetch_data,
    )

    process_step = FunctionStep(
        step_id="process",
        metadata=StepMetadata(name="Process Data", description="Run LLM processing"),
        input_type=DataOutput,
        output_type=DataOutput,
        func=process_data,
    )

    validate_step = FunctionStep(
        step_id="validate",
        metadata=StepMetadata(name="Validate Data", description="Validate results"),
        input_type=DataOutput,
        output_type=DataOutput,
        func=validate_data,
    )

    save_step = FunctionStep(
        step_id="save",
        metadata=StepMetadata(name="Save Data", description="Save to database"),
        input_type=DataOutput,
        output_type=DataOutput,
        func=save_data,
    )

    return Workflow(metadata=WorkflowMetadata(name="Data Pipeline", version="1.0.0")).chain(
        fetch_step, process_step, validate_step, save_step
    )


# ============================================================================
# Example 1: Fresh Run with Auto-Checkpointing
# ============================================================================


async def example_fresh_run_with_checkpoints():
    """Run workflow from scratch with auto-checkpointing enabled."""
    print("\n" + "=" * 70)
    print("Example 1: Fresh Run with Auto-Checkpointing")
    print("=" * 70 + "\n")

    # Setup checkpoint storage
    checkpoint_dir = Path("./checkpoints")
    store = FileCheckpointStore(base_path=checkpoint_dir)

    # Configure auto-save after each step
    config = CheckpointConfig(
        store=store,
        auto_save=True,
        save_interval_steps=1,  # Save after every step
    )

    # Build and run workflow
    workflow = build_workflow()
    runner = WorkflowRunner()

    print("🚀 Starting workflow with auto-checkpointing...\n")

    async for event in runner.run_stream(
        workflow=workflow,
        initial_input={"text": "customer_feedback.csv"},
        checkpoint_config=config,
    ):
        # Print key events
        if event.event_type in [
            "workflow_started",
            "step_completed",
            "checkpoint_saved",
            "workflow_completed",
        ]:
            print(f"   {event}")

    print(f"\n✨ Checkpoints saved to: {checkpoint_dir / workflow.id}")
    print(f"   (View checkpoint JSON files in that directory)")


# ============================================================================
# Example 2: Simulated Failure and Resume
# ============================================================================


async def example_resume_after_failure():
    """Simulate workflow failure and resume from checkpoint."""
    print("\n" + "=" * 70)
    print("Example 2: Simulated Failure and Resume")
    print("=" * 70 + "\n")

    checkpoint_dir = Path("./checkpoints")
    store = FileCheckpointStore(base_path=checkpoint_dir)
    config = CheckpointConfig(store=store, auto_save=True, save_interval_steps=1)

    workflow = build_workflow()
    runner = WorkflowRunner()

    print("🚀 Starting workflow (will fail after 2 steps)...\n")

    # Run until 2 checkpoints saved (simulate failure)
    checkpoint_count = 0
    try:
        async for event in runner.run_stream(
            workflow=workflow,
            initial_input={"text": "sales_data.csv"},
            checkpoint_config=config,
        ):
            if event.event_type in ["step_completed", "checkpoint_saved"]:
                print(f"   {event}")

            if event.event_type == "checkpoint_saved":
                checkpoint_count += 1
                if checkpoint_count == 2:
                    print("\n❌ Simulating failure after 2 steps!\n")
                    break
    except Exception:
        pass

    # Load checkpoint and resume
    print("🔄 Resuming from checkpoint...\n")

    checkpoint = await store.load_latest(workflow.id)
    if checkpoint:
        print(
            f"   Found checkpoint: {len(checkpoint.completed_step_ids)} steps completed"
        )
        print(f"   Completed: {checkpoint.completed_step_ids}")
        print(f"   Pending: {checkpoint.pending_step_ids}\n")

        # Resume from checkpoint
        async for event in runner.run_stream(
            workflow=workflow,
            initial_input={"text": "sales_data.csv"},
            checkpoint=checkpoint,  # Resume from here
            checkpoint_config=config,
        ):
            if event.event_type in [
                "workflow_resumed",
                "step_completed",
                "workflow_completed",
            ]:
                print(f"   {event}")

        print("\n✅ Workflow completed by resuming from checkpoint!")
        print("   (Only remaining steps were executed)")


# ============================================================================
# Example 3: Checkpoint Cleanup
# ============================================================================


async def example_checkpoint_cleanup():
    """Demonstrate automatic checkpoint cleanup."""
    print("\n" + "=" * 70)
    print("Example 3: Checkpoint Cleanup")
    print("=" * 70 + "\n")

    checkpoint_dir = Path("./checkpoints")
    store = FileCheckpointStore(base_path=checkpoint_dir)

    # Configure with auto-cleanup
    config = CheckpointConfig(
        store=store,
        auto_save=True,
        save_interval_steps=1,
        auto_cleanup=True,
        keep_last_n=3,  # Keep only 3 most recent checkpoints
    )

    workflow = build_workflow()
    runner = WorkflowRunner()

    print("🚀 Running workflow with auto-cleanup (keep last 3 checkpoints)...\n")

    async for event in runner.run_stream(
        workflow=workflow,
        initial_input={"text": "product_reviews.csv"},
        checkpoint_config=config,
    ):
        if event.event_type in ["checkpoint_saved", "workflow_completed"]:
            print(f"   {event}")

    # List remaining checkpoints
    metadata = await store.list_metadata(workflow_id=workflow.id)
    print(f"\n📋 Checkpoints remaining: {len(metadata)}")
    for meta in metadata:
        print(f"   - {meta.checkpoint_id[:8]}... ({meta.completed_steps}/{meta.total_steps} steps)")


# ============================================================================
# Main
# ============================================================================


async def main():
    """Run all examples."""
    print("\n🎯 Workflow Checkpoint Examples\n")

    # Example 1: Fresh run with auto-save
    await example_fresh_run_with_checkpoints()

    # Example 2: Resume after failure
    await example_resume_after_failure()

    # Example 3: Auto-cleanup
    await example_checkpoint_cleanup()

    print("\n" + "=" * 70)
    print("✨ All examples completed!")
    print("=" * 70)
    print("\n💡 Key Takeaways:")
    print("   1. Checkpoints auto-save after each step (configurable)")
    print("   2. Resume from checkpoint skips completed expensive steps")
    print("   3. Workflow structure validation ensures safe resume")
    print("   4. Auto-cleanup prevents unbounded checkpoint growth")
    print("\n📁 Check ./checkpoints/ directory for saved checkpoints")


if __name__ == "__main__":
    asyncio.run(main())
