"""DashScope native API helpers (non-OpenAI-compatible endpoints)."""

from __future__ import annotations

import httpx

from auteur.config import settings

BASE = "https://dashscope-intl.aliyuncs.com"

_STATUS_MAP = {
    "PENDING": "pending",
    "RUNNING": "running",
    "SUCCEEDED": "succeeded",
    "FAILED": "failed",
    "CANCELED": "canceled",
}


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.dashscope_api_key}"}


async def fetch_task(task_id: str) -> dict:
    """Fetch a DashScope task and normalise its status for poll_until_done.

    poll_until_done expects {"status": "succeeded"|"failed"|"canceled"|...}.
    DashScope returns {"output": {"task_status": "SUCCEEDED", ...}}.
    """
    async with httpx.AsyncClient(base_url=BASE, timeout=15) as client:
        resp = await client.get(f"/api/v1/tasks/{task_id}", headers=_auth())
        resp.raise_for_status()
        body = resp.json()

    raw = body.get("output", {}).get("task_status", "PENDING")
    return {**body, "status": _STATUS_MAP.get(raw, raw.lower())}
