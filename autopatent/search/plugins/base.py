from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class RequestSpec:
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    timeout_sec: int = 20
    meta: dict[str, Any] = field(default_factory=dict)


class SearchSitePlugin(Protocol):
    def plugin_id(self) -> str: ...

    def supports(self, query: str, topic: str) -> bool: ...

    def build_requests(self, query: str, topic: str, limit: int) -> list[RequestSpec]: ...

    def parse_response(self, payload: str | bytes, request: RequestSpec) -> list[dict[str, Any]]: ...

    def fallback_urls(self, query: str, topic: str, limit: int) -> list[str]: ...

    def parse_fallback(
        self,
        payload: str,
        url: str,
        query: str,
        source: str,
    ) -> list[dict[str, Any]]: ...
