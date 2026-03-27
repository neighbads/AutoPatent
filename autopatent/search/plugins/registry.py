from __future__ import annotations

from typing import Iterable

from autopatent.search.plugins.arxiv_plugin import ArxivPlugin
from autopatent.search.plugins.base import SearchSitePlugin
from autopatent.search.plugins.crossref_plugin import CrossrefPlugin
from autopatent.search.plugins.epo_ops_plugin import EpoOpsPlugin
from autopatent.search.plugins.openalex_plugin import OpenAlexPlugin
from autopatent.search.plugins.semantic_scholar_plugin import SemanticScholarPlugin


def _builtin_plugins() -> dict[str, SearchSitePlugin]:
    plugins: list[SearchSitePlugin] = [
        OpenAlexPlugin(),
        ArxivPlugin(),
        SemanticScholarPlugin(),
        CrossrefPlugin(),
        EpoOpsPlugin(),
    ]
    return {plugin.plugin_id(): plugin for plugin in plugins}


def builtin_plugin_ids() -> list[str]:
    return sorted(_builtin_plugins().keys())


def resolve_plugins(plugin_ids: Iterable[str]) -> list[SearchSitePlugin]:
    registry = _builtin_plugins()
    resolved: list[SearchSitePlugin] = []
    unknown: list[str] = []
    for raw in plugin_ids:
        plugin_id = str(raw or "").strip()
        if not plugin_id:
            continue
        plugin = registry.get(plugin_id)
        if plugin is None:
            unknown.append(plugin_id)
            continue
        resolved.append(plugin)
    if unknown:
        raise ValueError("Unknown search plugin ids: " + ", ".join(sorted(set(unknown))))
    return resolved
