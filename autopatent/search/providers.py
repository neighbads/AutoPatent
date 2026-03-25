from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, List, Protocol


class SearchProvider(Protocol):
    name: str

    def collect(
        self,
        *,
        topic: str,
        resources: List[Dict[str, str]],
        queries: List[str],
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]: ...


@dataclass(frozen=True)
class OfflinePseudoProvider:
    name: str = "offline"

    def collect(
        self,
        *,
        topic: str,
        resources: List[Dict[str, str]],
        queries: List[str],
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        direction_ids = [str(c.get("id")) for c in candidates if "id" in c]
        hits: List[Dict[str, Any]] = []
        if not queries or not resources:
            return hits

        sampled_queries = queries[: min(6, len(queries))]
        sampled_resources = resources[: min(10, len(resources))]
        for q_idx, query in enumerate(sampled_queries, start=1):
            for r_idx, resource in enumerate(sampled_resources, start=1):
                duplicate_bucket = (q_idx % 3) + 1
                title = f"{topic or '主题'} 相关方案 {duplicate_bucket}"
                hits.append(
                    {
                        "source": resource.get("source"),
                        "endpoint": resource.get("endpoint"),
                        "query": query,
                        "title": title,
                        "related_direction_ids": direction_ids,
                        "rank": r_idx,
                    }
                )
        return hits


@dataclass(frozen=True)
class SeedOnlyProvider:
    name: str = "seed-only"

    def collect(
        self,
        *,
        topic: str,
        resources: List[Dict[str, str]],
        queries: List[str],
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        hits: List[Dict[str, Any]] = []
        direction_ids = [str(c.get("id")) for c in candidates if "id" in c]
        if not queries:
            return hits
        fallback_source = resources[0]["source"] if resources else "SEED"
        fallback_endpoint = resources[0]["endpoint"] if resources else ""
        for idx, query in enumerate(queries, start=1):
            hits.append(
                {
                    "source": fallback_source,
                    "endpoint": fallback_endpoint,
                    "query": query,
                    "title": f"{topic or '主题'} seed result {idx}",
                    "related_direction_ids": direction_ids,
                    "rank": idx,
                }
            )
        return hits


@dataclass(frozen=True)
class OnlineSearchProvider:
    """Live network search provider using public paper indexes.

    Notes:
    - Uses OpenAlex and arXiv public endpoints.
    - Honors process proxy/no_proxy env vars via urllib defaults.
    - Never raises on transient network failures; returns partial hits.
    """

    name: str = "online"
    timeout_sec: int = 20
    max_retries: int = 2
    max_queries: int = 4
    max_results_per_source: int = 3
    user_agent: str = "AutoPatent/0.1 (+https://local.autopatent)"

    def collect(
        self,
        *,
        topic: str,
        resources: List[Dict[str, str]],
        queries: List[str],
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not queries:
            return []
        direction_ids = [str(c.get("id")) for c in candidates if "id" in c]
        sampled_queries = queries[: min(self.max_queries, len(queries))]

        hits: List[Dict[str, Any]] = []
        for query in sampled_queries:
            for query_variant in self._query_variants(query):
                hits.extend(
                    self._fetch_openalex(
                        query=query_variant,
                        endpoint=_resource_endpoint(
                            resources,
                            source="OPENALEX",
                            fallback="https://api.openalex.org/works",
                        ),
                        direction_ids=direction_ids,
                    )
                )
                hits.extend(
                    self._fetch_arxiv(
                        query=query_variant,
                        endpoint=_arxiv_api_endpoint(
                            _resource_endpoint(
                                resources,
                                source="ARXIV",
                                fallback="http://export.arxiv.org/api/query",
                            )
                        ),
                        direction_ids=direction_ids,
                    )
                )
        return hits

    def _fetch_openalex(
        self,
        *,
        query: str,
        endpoint: str,
        direction_ids: List[str],
    ) -> List[Dict[str, Any]]:
        url = (
            endpoint
            + "?"
            + urllib.parse.urlencode(
                {
                    "search": query,
                    "per_page": self.max_results_per_source,
                    "select": "id,title,publication_year,doi,primary_location",
                }
            )
        )
        payload = self._http_get_json(url)
        if not isinstance(payload, dict):
            return []
        results = payload.get("results")
        if not isinstance(results, list):
            return []
        hits: List[Dict[str, Any]] = []
        for idx, item in enumerate(results, start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            if not self._title_matches_query(title=title, query=query):
                continue
            landing = ""
            primary_location = item.get("primary_location")
            if isinstance(primary_location, dict):
                landing = str(primary_location.get("landing_page_url", "") or "").strip()
            doi = str(item.get("doi", "") or "").strip()
            doc_url = landing or doi or str(item.get("id", "") or "").strip()
            hits.append(
                {
                    "source": "OPENALEX",
                    "endpoint": endpoint,
                    "query": query,
                    "title": title,
                    "url": doc_url,
                    "year": item.get("publication_year"),
                    "related_direction_ids": direction_ids,
                    "rank": idx,
                }
            )
        return hits

    def _fetch_arxiv(
        self,
        *,
        query: str,
        endpoint: str,
        direction_ids: List[str],
    ) -> List[Dict[str, Any]]:
        encoded_query = urllib.parse.quote_plus(query)
        url = (
            f"{endpoint}?search_query=all:{encoded_query}"
            f"&start=0&max_results={self.max_results_per_source}"
            "&sortBy=relevance&sortOrder=descending"
        )
        xml_text = self._http_get_text(url)
        if not xml_text:
            return []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        hits: List[Dict[str, Any]] = []
        for idx, entry in enumerate(entries, start=1):
            title = self._clean_xml_text(entry.findtext("atom:title", default="", namespaces=ns))
            if not title:
                continue
            if not self._title_matches_query(title=title, query=query):
                continue
            link = self._clean_xml_text(entry.findtext("atom:id", default="", namespaces=ns))
            year = ""
            published = self._clean_xml_text(
                entry.findtext("atom:published", default="", namespaces=ns)
            )
            if len(published) >= 4 and published[:4].isdigit():
                year = published[:4]
            hits.append(
                {
                    "source": "ARXIV",
                    "endpoint": endpoint,
                    "query": query,
                    "title": title,
                    "url": link,
                    "year": year,
                    "related_direction_ids": direction_ids,
                    "rank": idx,
                }
            )
        return hits

    @staticmethod
    def _clean_xml_text(value: str) -> str:
        return " ".join(str(value or "").strip().split())

    def _http_get_json(self, url: str) -> Any:
        text = self._http_get_text(url)
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def _http_get_text(self, url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        retries = max(0, int(self.max_retries))
        for attempt in range(retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                    body = resp.read()
                return body.decode("utf-8", errors="ignore")
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
                if attempt >= retries:
                    return ""
                time.sleep(1.0 + attempt)
        return ""

    def _query_variants(self, query: str) -> List[str]:
        cleaned = " ".join(str(query or "").strip().split())
        if not cleaned:
            return []

        variants: List[str] = [cleaned]
        mapped = cleaned
        mapping = {
            "抗量子": "post-quantum",
            "后量子": "post-quantum",
            "量子安全": "quantum-safe",
            "证书": "certificate",
            "国密": "chinese cryptography",
            "混合": "hybrid",
            "协商": "negotiation",
            "握手": "handshake",
            "隧道": "tunnel",
            "密钥": "key",
            "交换": "exchange",
            "签名": "signature",
        }
        for cn, en in mapping.items():
            if cn in mapped:
                mapped = mapped.replace(cn, f" {en} ")

        ascii_tokens = re.findall(r"[A-Za-z0-9_\-/+.]+", mapped)
        ascii_phrase = " ".join(dict.fromkeys(tok for tok in ascii_tokens if len(tok) > 1))
        if ascii_phrase and ascii_phrase.lower() != cleaned.lower():
            variants.append(ascii_phrase)

        text_lower = cleaned.lower()
        if any(k in cleaned for k in ("抗量子", "后量子")) and any(
            k in text_lower for k in ("ssl", "tls", "ipsec")
        ):
            variants.append("post-quantum SSL TLS certificate handshake")
            variants.append("post-quantum IPsec key exchange")

        # Keep insertion order and remove empties.
        normalized: List[str] = []
        seen = set()
        for item in variants:
            q = " ".join(item.strip().split())
            if not q:
                continue
            key = q.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(q)
        return normalized[:3]

    def _title_matches_query(self, *, title: str, query: str) -> bool:
        title_lower = str(title or "").lower()
        if not title_lower:
            return False
        query_tokens = re.findall(r"[a-z0-9]{3,}", str(query or "").lower())
        if not query_tokens:
            return True

        expanded: List[str] = []
        for token in query_tokens:
            if token in ("ssl", "tls"):
                expanded.extend(["ssl", "tls", "handshake", "x509", "certificate"])
                continue
            if token == "ipsec":
                expanded.extend(["ipsec", "ike", "ikev2", "vpn"])
                continue
            if token == "post":
                continue
            expanded.append(token)

        dedup_tokens = list(dict.fromkeys(expanded))
        if not dedup_tokens:
            return True
        return any(tok in title_lower for tok in dedup_tokens)


def _resource_endpoint(resources: List[Dict[str, str]], *, source: str, fallback: str) -> str:
    source_norm = source.strip().upper()
    for resource in resources:
        src = str(resource.get("source", "")).strip().upper()
        endpoint = str(resource.get("endpoint", "")).strip()
        if src == source_norm and endpoint:
            return endpoint
    return fallback


def _arxiv_api_endpoint(endpoint: str) -> str:
    text = str(endpoint or "").strip()
    if not text:
        return "http://export.arxiv.org/api/query"
    lower = text.lower()
    if "export.arxiv.org/api/query" in lower:
        return text
    if "arxiv.org" in lower:
        return "http://export.arxiv.org/api/query"
    return text


def get_search_provider(name: str | None) -> SearchProvider:
    normalized = str(name or "").strip().lower() or "offline"
    if normalized == "offline":
        return OfflinePseudoProvider()
    if normalized == "seed-only":
        return SeedOnlyProvider()
    if normalized in ("online", "live", "live-web", "network"):
        return OnlineSearchProvider()
    raise ValueError(f"Unknown search provider: {normalized}")
