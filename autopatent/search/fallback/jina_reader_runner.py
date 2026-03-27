from __future__ import annotations

import urllib.parse
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class FallbackResult:
    status: str
    source: str
    content: str = ""
    error: str = ""
    url: str = ""


def wrap_jina_reader_url(target_url: str) -> str:
    candidate = str(target_url or "").strip()
    if not candidate:
        raise ValueError("target_url is required")
    parsed = urllib.parse.urlparse(candidate)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("target_url must use http or https")
    return f"https://r.jina.ai/{candidate}"


def run_jina_reader(*, target_url: str, timeout_sec: int, user_agent: str) -> FallbackResult:
    try:
        runner_url = wrap_jina_reader_url(target_url)
    except ValueError as exc:
        return FallbackResult(status="error", source="jina_reader", error=str(exc), url=str(target_url))

    req = urllib.request.Request(
        runner_url,
        headers={"User-Agent": user_agent},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=max(1, int(timeout_sec))) as resp:
            payload = resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:  # noqa: BLE001
        return FallbackResult(
            status="error",
            source="jina_reader",
            error=str(exc),
            url=runner_url,
        )

    if not payload.strip():
        return FallbackResult(
            status="error",
            source="jina_reader",
            error="empty payload",
            url=runner_url,
        )
    return FallbackResult(status="ok", source="jina_reader", content=payload, url=runner_url)
