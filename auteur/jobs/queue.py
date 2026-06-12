"""Bounded async job queue for concurrent video generation tasks."""

import asyncio
import logging
from typing import Any, Callable, Coroutine, TypeVar

from auteur.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class JobQueue:
    """Runs async jobs concurrently up to a configurable parallelism limit."""

    def __init__(self, max_concurrent: int | None = None) -> None:
        limit = max_concurrent or settings.parallel_shot_limit
        self._semaphore = asyncio.Semaphore(limit)

    async def run(self, coro: Coroutine[Any, Any, T]) -> T:
        """Acquire a slot, run the coroutine, then release."""
        async with self._semaphore:
            return await coro

    async def run_all(
        self,
        tasks: list[Callable[[], Coroutine[Any, Any, T]]],
    ) -> list[T | BaseException]:
        """Run all task factories concurrently, respecting the slot limit.

        Returns results in the same order as tasks. Exceptions are returned
        as values rather than raised so one failure doesn't cancel siblings.
        """
        coros = [self.run(factory()) for factory in tasks]
        return await asyncio.gather(*coros, return_exceptions=True)
