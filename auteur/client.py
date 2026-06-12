"""Shared DashScope client factory."""

from openai import AsyncOpenAI

from auteur.config import settings


def dashscope_client() -> AsyncOpenAI:
    """Return an AsyncOpenAI client pointed at the DashScope Singapore endpoint."""
    return AsyncOpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )
