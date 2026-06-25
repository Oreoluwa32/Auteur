"""Smoke test: single Qwen chat completion.

Verifies API key, endpoint, and model are correctly configured.
Run: python scripts/smoke/smoke_qwen.py
"""

import asyncio
import os
import sys
import time

from _env import load_dotenv

load_dotenv()


async def main() -> None:
    from openai import AsyncOpenAI

    key = os.getenv("DASHSCOPE_API_KEY", "")
    if not key or key == "sk-...":
        print("✗ DASHSCOPE_API_KEY not set — copy .env.example to .env and fill it in")
        sys.exit(1)

    base_url = os.getenv(
        "DASHSCOPE_BASE_URL",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
    model = os.getenv("MODEL_DIRECTOR", "qwen-max")

    print(f"endpoint : {base_url}")
    print(f"model    : {model}")
    print("sending  : 1 chat completion request …")

    client = AsyncOpenAI(api_key=key, base_url=base_url)
    t0 = time.monotonic()

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "Reply with exactly: AUTEUR_OK"},
        ],
        max_tokens=16,
        temperature=0,
    )

    elapsed = time.monotonic() - t0
    content = response.choices[0].message.content or ""
    usage = response.usage

    print(f"response : {content.strip()!r}")
    print(f"tokens   : {usage.prompt_tokens} in / {usage.completion_tokens} out" if usage else "tokens   : (no usage data)")
    print(f"latency  : {elapsed:.2f}s")

    if "AUTEUR_OK" in content:
        print("\n✓ Qwen smoke test passed")
    else:
        print("\n⚠ unexpected response — check model/endpoint")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
