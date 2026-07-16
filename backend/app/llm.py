"""Shared LLM client — xAI Grok (OpenAI-compatible API)."""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.config import get_settings

XAI_BASE_URL = "https://api.x.ai/v1"


def llm_configured() -> bool:
    return bool(get_settings().xai_api_key)


def get_chat_llm(temperature: float = 0) -> ChatOpenAI | None:
    settings = get_settings()
    if not settings.xai_api_key:
        return None
    return ChatOpenAI(
        api_key=settings.xai_api_key,
        base_url=XAI_BASE_URL,
        model=settings.llm_model,
        temperature=temperature,
    )
