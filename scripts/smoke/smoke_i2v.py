"""Smoke test: image-to-video task creation and polling.

Uses the image saved by smoke_image.py as input. Reveals the real
DashScope i2v API response shape so generate.py can be adjusted.

Run: python scripts/smoke/smoke_image.py && python scripts/smoke/smoke_i2v.py
"""

import asyncio
import base64
import json
import os
import sys
import time
from pathlib import Path


# DashScope's video generation is NOT on the OpenAI-compatible endpoint —
# it lives at a different path. We call it directly via httpx and print
# the raw response so we can lock down the exact shape.
_I2V_CREATE_PATH = "/api/v1/services/aigc/video-generation/video-synthesis"
_I2V_QUERY_PATH  = "/api/v1/tasks/{task_id}"
_DASHSCOPE_BASE  = "https://dashscope-intl.aliyuncs.com"


async def main() -> None:
    import httpx

    key = os.getenv("DASHSCOPE_API_KEY", "")
    if not key or key == "sk-...":
        print("✗ DASHSCOPE_API_KEY not set")
        sys.exit(1)

    model = os.getenv("MODEL_I2V", "wan2.1-i2v-turbo")
    image_path = Path("/tmp/auteur_smoke_image.png")

    if not image_path.exists():
        print(f"✗ {image_path} not found — run smoke_image.py first")
        sys.exit(1)

    image_b64 = base64.b64encode(image_path.read_bytes()).decode()
    image_data_uri = f"data:image/png;base64,{image_b64}"

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",   # required for async task creation
    }

    payload = {
        "model": model,
        "input": {
            "image": image_data_uri,
            "prompt": "The apple rolls gently to the right",
        },
        "parameters": {
            "duration": 5,
        },
    }

    print(f"model    : {model}")
    print(f"image    : {image_path} ({image_path.stat().st_size:,} bytes)")
    print(f"creating task at {_DASHSCOPE_BASE}{_I2V_CREATE_PATH} …")

    async with httpx.AsyncClient(base_url=_DASHSCOPE_BASE, timeout=30) as client:
        t0 = time.monotonic()
        resp = await client.post(_I2V_CREATE_PATH, headers=headers, json=payload)
        elapsed = time.monotonic() - t0

    print(f"\nHTTP {resp.status_code}  ({elapsed:.2f}s)")
    print("── raw response ────────────────────────────────────")
    try:
        body = resp.json()
        print(json.dumps(body, indent=2))
    except Exception:
        print(resp.text)
    print("──────────────────────────────────────────────────")

    if resp.status_code not in (200, 202):
        print(f"\n✗ Task creation failed (HTTP {resp.status_code})")
        sys.exit(1)

    body = resp.json()
    # Try common key locations for task_id
    task_id = (
        body.get("output", {}).get("task_id")
        or body.get("request_id")
        or body.get("task_id")
    )

    if not task_id:
        print("\n⚠ Could not locate task_id in response — inspect output above")
        print("  Update generate.py to match the actual response shape.")
        sys.exit(0)

    print(f"\ntask_id  : {task_id}")
    print("polling  : checking status (one poll, no wait) …")

    poll_url = _I2V_QUERY_PATH.format(task_id=task_id)
    async with httpx.AsyncClient(base_url=_DASHSCOPE_BASE, timeout=15) as client:
        poll_resp = await client.get(poll_url, headers={"Authorization": f"Bearer {key}"})

    print(f"\nHTTP {poll_resp.status_code}")
    print("── poll response ───────────────────────────────────")
    try:
        print(json.dumps(poll_resp.json(), indent=2))
    except Exception:
        print(poll_resp.text)
    print("──────────────────────────────────────────────────")
    print("\n✓ i2v task created and polled — update generate.py with the shape above")


if __name__ == "__main__":
    asyncio.run(main())
