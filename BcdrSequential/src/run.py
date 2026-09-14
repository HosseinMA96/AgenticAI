"""CLI entry point: python -m src.run --service <id>

M1 scope: fresh run only, streaming events printed per step. --resume and
--export-graph land in Phase 4 (durability).
"""

import argparse
import asyncio

from src.graph import build_graph


async def run(service_id: str) -> None:
    workflow = build_graph()
    stream = workflow.run(service_id, stream=True)
    async for event in stream:
        print(f"[{event.type:>20}] executor={event.executor_id} data={event.data!r}")

    result = await stream.get_final_response()
    for packet in result.get_outputs():
        print("\n--- Evidence Packet ---")
        print(packet.markdown)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the compliance evidence workflow")
    parser.add_argument("--service", required=True, help="Service id under fixtures/")
    args = parser.parse_args()
    asyncio.run(run(args.service))


if __name__ == "__main__":
    main()
