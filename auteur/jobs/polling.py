"""Async polling loop for long-running video generation tasks."""

import asyncio
import logging
from typing import Any, Callable, Coroutine

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from auteur.config import settings

logger = logging.getLogger(__name__)


class JobTimeoutError(Exception):
    """Raised when a job exceeds the configured timeout."""


class JobFailedError(Exception):
    """Raised when a job reports a terminal failure status."""


async def poll_until_done(
    task_id: str,
    fetch_status: Callable[[str], Coroutine[Any, Any, dict]],
    *,
    poll_interval: int | None = None,
    timeout: int | None = None,
) -> dict:
    """Poll a task until it reaches a terminal state.

    Args:
        task_id: Provider task identifier.
        fetch_status: Async callable that takes a task_id and returns a status dict.
            Expected keys: "status" (str), optionally "output" and "error".
        poll_interval: Seconds between polls. Defaults to settings.job_poll_interval.
        timeout: Max seconds to wait. Defaults to settings.job_timeout.

    Returns:
        The final status dict from fetch_status once status is "succeeded".

    Raises:
        JobFailedError: Task reported a failure status.
        JobTimeoutError: Task did not complete within the timeout.
    """
    interval = poll_interval if poll_interval is not None else settings.job_poll_interval
    deadline = timeout if timeout is not None else settings.job_timeout

    elapsed = 0
    while elapsed < deadline:
        result = await fetch_status(task_id)
        status = result.get("status", "")

        if status == "succeeded":
            logger.info("task %s succeeded", task_id)
            return result

        if status in ("failed", "canceled"):
            raise JobFailedError(f"Task {task_id} ended with status={status}: {result.get('error')}")

        logger.debug("task %s status=%s, waiting %ds", task_id, status, interval)
        await asyncio.sleep(interval)
        elapsed += interval

    raise JobTimeoutError(f"Task {task_id} timed out after {deadline}s")


@retry(
    retry=retry_if_exception_type(ConnectionError),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=16),
    reraise=True,
)
async def fetch_with_retry(
    fetch_fn: Callable[[str], Coroutine[Any, Any, dict]],
    task_id: str,
) -> dict:
    """Wrap a single status fetch with exponential-backoff retries on transient errors."""
    return await fetch_fn(task_id)
