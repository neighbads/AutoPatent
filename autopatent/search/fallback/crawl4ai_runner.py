from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass


@dataclass(frozen=True)
class FallbackResult:
    status: str
    source: str
    content: str = ""
    error: str = ""
    url: str = ""


def run_crawl4ai(*, target_url: str, timeout_sec: int) -> FallbackResult:
    try:
        import crawl4ai  # type: ignore
    except Exception:  # noqa: BLE001
        return FallbackResult(
            status="fallback_unavailable",
            source="crawl4ai",
            error="crawl4ai not installed",
            url=target_url,
        )

    try:
        content = _run_best_effort(crawl4ai, target_url=target_url, timeout_sec=timeout_sec)
    except Exception as exc:  # noqa: BLE001
        return FallbackResult(status="error", source="crawl4ai", error=str(exc), url=target_url)

    if not str(content or "").strip():
        return FallbackResult(
            status="error",
            source="crawl4ai",
            error="empty payload",
            url=target_url,
        )
    return FallbackResult(status="ok", source="crawl4ai", content=str(content), url=target_url)


def _run_best_effort(crawl4ai_module: object, *, target_url: str, timeout_sec: int) -> str:
    if hasattr(crawl4ai_module, "AsyncWebCrawler"):
        crawler_cls = getattr(crawl4ai_module, "AsyncWebCrawler")

        async def _runner() -> str:
            async with crawler_cls() as crawler:
                result = await crawler.arun(url=target_url, timeout=max(1, int(timeout_sec)))
                for field in ("markdown", "text", "html"):
                    value = getattr(result, field, "")
                    if isinstance(value, str) and value.strip():
                        return value
                return str(result)

        return asyncio.run(_runner())

    if hasattr(crawl4ai_module, "WebCrawler"):
        crawler = getattr(crawl4ai_module, "WebCrawler")()
        run_callable = getattr(crawler, "run", None)
        if run_callable is None or not callable(run_callable):
            raise RuntimeError("crawl4ai.WebCrawler.run is unavailable")
        sig = inspect.signature(run_callable)
        if "url" in sig.parameters:
            result = run_callable(url=target_url)
        else:
            result = run_callable(target_url)
        for field in ("markdown", "text", "html"):
            value = getattr(result, field, "")
            if isinstance(value, str) and value.strip():
                return value
        return str(result)

    raise RuntimeError("crawl4ai integration entry not found")
