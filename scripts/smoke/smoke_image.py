"""Smoke test: single Wan image generation via DashScope native API.

Generates a test image and saves it to the system temp directory.
Run: python scripts/smoke/smoke_image.py
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from _env import load_dotenv

load_dotenv()

_T2I_PATH = "/api/v1/services/aigc/text2image/image-synthesis"
_TASK_PATH = "/api/v1/tasks/{task_id}"
_DASHSCOPE_BASE = "https://dashscope-intl.aliyuncs.com"

SMOKE_IMAGE = Path(tempfile.gettempdir()) / "auteur_smoke_image.png"


async def main() -> None:
    import httpx

    key = os.getenv("DASHSCOPE_API_KEY", "")
    if not key or key == "sk-...":
        print("✗ DASHSCOPE_API_KEY not set")
        sys.exit(1)

    model = os.getenv("MODEL_IMAGE", "wanx2.1-t2i-turbo")

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    payload = {
        "model": model,
        "input": {"prompt": "A single red apple on a white background, photorealistic"},
        "parameters": {"size": "1024*1024", "n": 1},
    }

    print(f"model    : {model}")
    print(f"creating task at {_DASHSCOPE_BASE}{_T2I_PATH} …")

    async with httpx.AsyncClient(base_url=_DASHSCOPE_BASE, timeout=30) as client:
        t0 = time.monotonic()
        resp = await client.post(_T2I_PATH, headers=headers, json=payload)
        elapsed = time.monotonic() - t0

    print(f"\nHTTP {resp.status_code}  ({elapsed:.2f}s)")
    print("── raw create response ────────────────────────────────────")
    try:
        body = resp.json()
        print(json.dumps(body, indent=2))
    except Exception:
        print(resp.text)
    print("────────────────────────────────────────────────────────")

    if resp.status_code not in (200, 202):
        print(f"\n✗ Task creation failed (HTTP {resp.status_code})")
        sys.exit(1)

    body = resp.json()
    task_id = body.get("output", {}).get("task_id")
    if not task_id:
        print("\n⚠ Could not locate task_id — inspect output above")
        sys.exit(0)

    print(f"\ntask_id  : {task_id}")
    print("polling  : waiting for SUCCEEDED (image gen takes ~20–60s) …")

    poll_headers = {"Authorization": f"Bearer {key}"}
    poll_url = _TASK_PATH.format(task_id=task_id)

    async with httpx.AsyncClient(base_url=_DASHSCOPE_BASE, timeout=300) as client:
        for _ in range(30):
            await asyncio.sleep(10)
            poll_resp = await client.get(poll_url, headers=poll_headers)
            poll_body = poll_resp.json()
            status = poll_body.get("output", {}).get("task_status", "")
            print(f"  status : {status}")

            if status == "SUCCEEDED":
                print("\n── poll response ──────────────────────────────────")
                print(json.dumps(poll_body, indent=2))
                print("────────────────────────────────────────────────")

                results = poll_body.get("output", {}).get("results", [])
                url = results[0].get("url") if results else None
                if url:
                    img = await client.get(url, follow_redirects=True)
                    SMOKE_IMAGE.write_bytes(img.content)
                    print(f"\nsaved    : {SMOKE_IMAGE} ({len(img.content):,} bytes)")
                    print("\n✓ Image smoke test passed")
                else:
                    print(f"\n⚠ No URL in response: {poll_body}")
                    sys.exit(1)
                return

            if status in ("FAILED", "CANCELED"):
                print("\n── poll response ──────────────────────────────────")
                print(json.dumps(poll_body, indent=2))
                print(f"\n✗ Task {status}")
                sys.exit(1)

    print("\n✗ Timed out waiting for image generation")
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
