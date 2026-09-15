"""CLI entry point: python -m src.run --service <id> [--threshold 0.6]

Phase 3 scope: fresh run only, streaming events printed per step. --resume
and --export-graph land in Phase 4 (durability).
"""

import argparse
import asyncio

from src.graph import build_graph
from src.models import RunRequest


async def run(service_id: str, confidence_threshold: float) -> None:
    workflow = build_graph()
    request = RunRequest(service_id=service_id, confidence_threshold=confidence_threshold)
    stream = workflow.run(request, stream=True)
    async for event in stream:
        data_repr = repr(event.data)
        if len(data_repr) > 120:
            data_repr = data_repr[:117] + "..."
        print(f"[{event.type:>20}] executor={event.executor_id} data={data_repr}")

    result = await stream.get_final_response()
    for packet in result.get_outputs():
        print("\n--- Evidence Packet ---")
        print(packet.markdown)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the compliance evidence workflow")
    parser.add_argument("--service", required=True, help="Service id under fixtures/")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.6,
        help="Confidence threshold below which a finding routes to human_review (default: 0.6)",
    )
    args = parser.parse_args()
    asyncio.run(run(args.service, args.threshold))


if __name__ == "__main__":
    main()
