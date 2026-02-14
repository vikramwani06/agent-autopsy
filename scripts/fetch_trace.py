"""Script to fetch all details about a specific Langfuse trace and dump to JSON."""

import asyncio
import base64
import json
import sys
from pathlib import Path

import httpx

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_autopsy.config import get_settings

TRACE_ID = "b448b0904d18d5a59d87df8cfcac4bc9"


async def fetch_trace_details(trace_id: str) -> dict:
    settings = get_settings()
    base_url = settings.langfuse_base_url.rstrip("/")
    credentials = f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}"
    auth_header = "Basic " + base64.b64encode(credentials.encode()).decode()
    headers = {"Authorization": auth_header}

    async with httpx.AsyncClient(timeout=30) as client:
        # 1. Fetch trace
        trace_resp = await client.get(
            f"{base_url}/api/public/traces/{trace_id}",
            headers=headers,
        )
        trace_resp.raise_for_status()
        trace_data = trace_resp.json()

        # 2. Fetch all observations (paginated)
        observations = []
        page = 1
        while True:
            obs_resp = await client.get(
                f"{base_url}/api/public/observations?traceId={trace_id}&page={page}&limit=100",
                headers=headers,
            )
            obs_resp.raise_for_status()
            batch = obs_resp.json().get("data", [])
            observations.extend(batch)
            if len(batch) < 100:
                break
            page += 1

    return {
        "trace": trace_data,
        "observations": observations,
        "observation_count": len(observations),
    }


async def main():
    print(f"Fetching trace {TRACE_ID}...")
    data = await fetch_trace_details(TRACE_ID)

    output_path = Path(__file__).resolve().parent / f"trace_{TRACE_ID[:12]}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

    print(f"Saved to {output_path}")
    print(f"Observations: {data['observation_count']}")

    # Print summary
    trace = data["trace"]
    print(f"\nTrace name: {trace.get('name')}")
    print(f"Trace input: {json.dumps(trace.get('input'), indent=2, default=str)[:500]}")
    print(f"Trace output: {json.dumps(trace.get('output'), indent=2, default=str)[:1000]}")
    print(f"Tags: {trace.get('tags')}")

    print("\n--- Observations Summary ---")
    for obs in data["observations"]:
        name = obs.get("name", "?")
        obs_type = obs.get("type", "?")
        level = obs.get("level", "?")
        model = obs.get("model", "")
        status_msg = obs.get("statusMessage", "")
        print(f"  [{obs_type}] {name} (level={level}, model={model})")
        if obs.get("input"):
            inp_str = json.dumps(obs["input"], default=str)
            print(f"    input: {inp_str[:200]}")
        if obs.get("output"):
            out_str = json.dumps(obs["output"], default=str)
            print(f"    output: {out_str[:300]}")
        if status_msg:
            print(f"    statusMessage: {status_msg}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
