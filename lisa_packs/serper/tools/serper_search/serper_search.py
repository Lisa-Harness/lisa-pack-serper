"""Serper.dev Search tool provider for the web_search contract.

Uses the Serper.dev REST API (POST https://google.serper.dev/search) with
``X-API-KEY`` header authentication.  The response ``organic`` array contains
objects with ``title``, ``link``, and ``snippet`` fields that are mapped to
the pack's generic ``WebSearchResult`` model.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import httpx
from kernel.models import ToolExecutionContext, ToolResult
from pydantic import BaseModel, Field

from lisa_packs.serper.models import WebSearchResponse, WebSearchResult

__all__ = ["Parameters", "execute", "is_configured", "search"]

_DEFAULT_ENDPOINT = "https://google.serper.dev/search"
_DEFAULT_NUM_RESULTS = 10
_SEARCH_TIMEOUT_SECONDS: float = 10.0


class Parameters(BaseModel):
    """Structured input parameters for the web_search tool."""

    query: str = Field(..., description="The search query to execute.")
    count: int = Field(default=10, ge=1, le=20, description="Max results per query.")


def _get_api_key() -> str:
    return os.environ.get("SERPER_SEARCH_API_KEY", "").strip()


def _get_endpoint() -> str:
    return (
        os.environ.get("SERPER_SEARCH_ENDPOINT", _DEFAULT_ENDPOINT).strip()
        or _DEFAULT_ENDPOINT
    )


def _get_num_results() -> int:
    raw = os.environ.get("SERPER_SEARCH_NUM_RESULTS", "").strip()
    if not raw:
        return _DEFAULT_NUM_RESULTS
    try:
        return max(1, min(20, int(raw)))
    except ValueError:
        return _DEFAULT_NUM_RESULTS


def is_configured() -> bool:
    """Return True when a Serper.dev search API key is present in the environment."""
    return bool(_get_api_key())


async def search(
    query: str, client: httpx.AsyncClient | None = None
) -> WebSearchResponse:
    """Execute one Serper.dev Search query and return structured results.

    Raises:
        RuntimeError: when SERPER_SEARCH_API_KEY is not configured.
        httpx.HTTPStatusError: when the search API returns a non-2xx response.
    """
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError(
            "Serper search is not configured. Set SERPER_SEARCH_API_KEY to enable it."
        )

    payload: dict[str, object] = {
        "q": query,
        "num": _get_num_results(),
    }
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": api_key,
    }

    async def _do_request(c: httpx.AsyncClient) -> WebSearchResponse:
        response = await c.post(
            _get_endpoint(),
            json=payload,
            headers=headers,
            timeout=_SEARCH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return _parse_response(query, response.json())

    if client is not None:
        return await _do_request(client)

    async with httpx.AsyncClient() as managed_client:
        return await _do_request(managed_client)


def _parse_response(query: str, data: dict) -> WebSearchResponse:
    raw_values: list[dict] = data.get("organic", [])

    results: list[WebSearchResult] = []
    for item in raw_values:
        url = item.get("link", "")
        if not url:
            continue
        results.append(
            WebSearchResult(
                name=item.get("title", ""),
                url=url,
                snippet=item.get("snippet", ""),
                display_url=url,
            )
        )

    return WebSearchResponse(
        query=query,
        generated_at=datetime.now(UTC).isoformat(),
        results=results,
    )


async def execute(ctx: ToolExecutionContext) -> ToolResult:
    """Execute the web_search tool — called by the tool registry dispatcher."""
    from pydantic import ValidationError

    try:
        params = Parameters.model_validate(ctx.parameters or {})
        query = params.query.strip()
    except ValidationError:
        query = ""
    if not query:
        query = (ctx.query or "").strip()
    if not query:
        return ToolResult(
            tool_id=ctx.tool_id or "web_search",
            error="web_search requires a query.",
        )

    if not is_configured():
        return ToolResult(
            tool_id=ctx.tool_id or "web_search",
            error="Serper search is not configured. Set SERPER_SEARCH_API_KEY to enable it.",
        )

    try:
        response = await search(query)
    except Exception as exc:  # noqa: BLE001  # broad-except is intentional at tool boundary
        return ToolResult(
            tool_id=ctx.tool_id or "web_search",
            error=f"Serper search failed: {type(exc).__name__}: {exc}",
        )

    return ToolResult(
        tool_id=ctx.tool_id or "web_search",
        output_text=render_search_results(response),
        output_json={"response": response.model_dump(mode="json")},
    )


def render_search_results(response: WebSearchResponse) -> str:
    """Render a WebSearchResponse as a text block for model consumption."""
    if not response.results:
        return f"No web results found for: {response.query}"

    lines: list[str] = []
    for i, result in enumerate(response.results, 1):
        lines.append(f"{i}. {result.name}")
        lines.append(f"   {result.display_url or result.url}")
        if result.snippet:
            lines.append(f"   {result.snippet}")
        lines.append("")
    lines.append(f"Serper Search | {len(response.results)} result(s)")
    return "\n".join(lines)
