"""Web search response models for the Serper provider pack."""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["WebSearchResponse", "WebSearchResult"]


class WebSearchResult(BaseModel):
    """One Serper.dev Search result item."""

    name: str
    url: str
    snippet: str = ""
    display_url: str = ""


class WebSearchResponse(BaseModel):
    """Structured response from one Serper.dev Search query."""

    query: str
    generated_at: str
    results: list[WebSearchResult] = Field(default_factory=list)