"""Smoke test: single Wan image generation.

Generates a 512x512 test image and saves it to /tmp/auteur_smoke_image.png.
Run: python scripts/smoke/smoke_image.py
"""

import asyncio
import os
import sys
import time
from pathlib import Path

from _env import load_dotenv

load_dotenv()


async def main() -> None:
    from openai import AsyncOpenAI

    key = os.getenv("DASHSCOPE_API_KEY", "")
    if not key or key == "sk-...":
        print("✗ DASHSCOPE_API_KEY not set")
        sys.exit(1)

    base_url = os.getenv(
        "DASHSCOPE_BASE_URL",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
    model = os.getenv("MODEL_IMAGE", "wanx2.1-t2i-turbo")

    print(f"endpoint : {base_url}")
    print(f"model    : {model}")
    print("sending  : image generation request …")

    client = AsyncOpenAI(api_key=key, base_url=base_url)
    t0 = time.monotonic()

    response = await client.images.generate(
        model=model,
        prompt="A single red apple on a white background, photorealistic",
        n=1,
        size="512x512",
    )

    elapsed = time.monotonic() - t0
    print(f"latency  : {elapsed:.2f}s")
    print(f"raw response type: {type(response)}")

    if response.data:
        img = response.data[0]
        url = img.url
        b64 = getattr(img, "b64_json", None)

        print(f"url      : {url}")
        print(f"b64_json : {'present' if b64 else 'absent'}")

        if url:
            import httpx
            async with httpx.AsyncClient() as http:
                r = await http.get(url, follow_redirects=True)
                r.raise_for_status()
                dest = Path("/tmp/auteur_smoke_image.png")
                dest.write_bytes(r.content)
                print(f"saved    : {dest} ({len(r.content):,} bytes)")
        elif b64:
            import base64
            dest = Path("/tmp/auteur_smoke_image.png")
            dest.write_bytes(base64.b64decode(b64))
            print(f"saved    : {dest}")

        print("\n✓ Image smoke test passed")
    else:
        print(f"\n✗ No image data in response: {response}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
