"""CLI entry point.

    python -m src.run --service <id> [--threshold 0.6]
    python -m src.run --service <id> --resume <checkpoint-id>
    python -m src.run --export-graph graph.json

Every fresh/resumed run is checkpointed to disk (checkpoints/, gitignored)
after each superstep. See graph.py and README for how --resume interacts
with human_review's blocking input() (the answer to brief §6 Q... covered
in NOTES.md).
"""

import argparse
import asyncio

from agent_framework import FileCheckpointStorage

from src.graph import WORKFLOW_NAME, build_graph
from src.models import RunRequest

CHECKPOINTS_DIR = "checkpoints"

# Checkpoints are pickled; the framework refuses to deserialize any type not
# explicitly allow-listed here, as a guard against arbitrary code execution
# from a tampered checkpoint file. Every Pydantic model that crosses a
# WorkflowContext edge (and can therefore end up embedded in a checkpoint)
# must be listed.
ALLOWED_CHECKPOINT_TYPES = [
    "src.models:RunRequest",
    "src.models:ArtifactSet",
    "src.models:EvidenceItem",
    "src.models:EvidenceFormat",
    "src.models:Finding",
    "src.models:FindingSet",
    "src.models:FindingStatus",
    "src.models:HumanReviewDecision",
    "src.models:EvidencePacket",
]


def _make_storage() -> FileCheckpointStorage:
    return FileCheckpointStorage(CHECKPOINTS_DIR, allowed_checkpoint_types=ALLOWED_CHECKPOINT_TYPES)


async def _drain(stream, storage: FileCheckpointStorage) -> None:
    async for event in stream:
        data_repr = repr(event.data)
        if len(data_repr) > 120:
            data_repr = data_repr[:117] + "..."
        print(f"[{event.type:>20}] executor={event.executor_id} data={data_repr}")

    result = await stream.get_final_response()
    for packet in result.get_outputs():
        print("\n--- Evidence Packet ---")
        print(packet.markdown)

    checkpoint_ids = await storage.list_checkpoint_ids(workflow_name=WORKFLOW_NAME)
    print(f"\nCheckpoints on disk for this workflow: {checkpoint_ids}")


async def run(service_id: str, confidence_threshold: float) -> None:
    storage = _make_storage()
    workflow = build_graph(checkpoint_storage=storage)
    request = RunRequest(service_id=service_id, confidence_threshold=confidence_threshold)
    stream = workflow.run(request, stream=True)
    await _drain(stream, storage)


async def resume(checkpoint_id: str) -> None:
    storage = _make_storage()
    workflow = build_graph(checkpoint_storage=storage)
    stream = workflow.run(checkpoint_id=checkpoint_id, checkpoint_storage=storage, stream=True)
    await _drain(stream, storage)


def export_graph(path: str) -> None:
    workflow = build_graph()
    with open(path, "w") as f:
        f.write(workflow.to_json())
    print(f"Wrote graph topology to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the compliance evidence workflow")
    parser.add_argument("--service", help="Service id under fixtures/")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.6,
        help="Confidence threshold below which a finding routes to human_review (default: 0.6)",
    )
    parser.add_argument("--resume", metavar="CHECKPOINT_ID", help="Resume a previous run from a checkpoint")
    parser.add_argument("--export-graph", metavar="PATH", help="Dump the graph topology to a JSON file and exit")
    args = parser.parse_args()

    if args.export_graph:
        export_graph(args.export_graph)
        return

    if args.resume:
        asyncio.run(resume(args.resume))
        return

    if not args.service:
        parser.error("--service is required for a fresh run")
    asyncio.run(run(args.service, args.threshold))


if __name__ == "__main__":
    main()
