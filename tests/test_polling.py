"""Tests for async job polling state transitions."""

import asyncio

import pytest

from auteur.jobs.polling import poll_until_done, JobFailedError, JobTimeoutError


async def _make_fetcher(responses: list[dict]):
    """Return an async fetch function that yields responses in order."""
    calls = iter(responses)

    async def fetch(task_id: str) -> dict:
        return next(calls)

    return fetch


@pytest.mark.asyncio
async def test_succeeds_immediately():
    fetch = await _make_fetcher([{"status": "succeeded", "output": {"url": "http://x"}}])
    result = await poll_until_done("t1", fetch, poll_interval=0, timeout=5)
    assert result["status"] == "succeeded"


@pytest.mark.asyncio
async def test_succeeds_after_pending():
    fetch = await _make_fetcher([
        {"status": "pending"},
        {"status": "running"},
        {"status": "succeeded", "output": {}},
    ])
    result = await poll_until_done("t1", fetch, poll_interval=0, timeout=10)
    assert result["status"] == "succeeded"


@pytest.mark.asyncio
async def test_raises_on_failed_status():
    fetch = await _make_fetcher([{"status": "failed", "error": "OOM"}])
    with pytest.raises(JobFailedError):
        await poll_until_done("t1", fetch, poll_interval=0, timeout=5)


@pytest.mark.asyncio
async def test_raises_on_timeout():
    async def always_pending(task_id: str) -> dict:
        return {"status": "running"}

    with pytest.raises(JobTimeoutError):
        await poll_until_done("t1", always_pending, poll_interval=0, timeout=1)


@pytest.mark.asyncio
async def test_raises_on_canceled():
    fetch = await _make_fetcher([{"status": "canceled"}])
    with pytest.raises(JobFailedError):
        await poll_until_done("t1", fetch, poll_interval=0, timeout=5)
