from __future__ import annotations

import pytest

from autopatent.search.plugins.registry import builtin_plugin_ids, resolve_plugins


def test_registry_loads_builtin_plugins():
    ids = builtin_plugin_ids()
    assert "openalex" in ids
    assert "arxiv" in ids
    assert "semantic_scholar" in ids
    assert "crossref" in ids
    assert "epo_ops" in ids


def test_registry_rejects_unknown_plugin():
    with pytest.raises(ValueError) as exc:
        resolve_plugins(["openalex", "not-exist"])
    assert "unknown search plugin ids" in str(exc.value).lower()


def test_registry_resolves_plugins_in_requested_order():
    plugins = resolve_plugins(["crossref", "openalex"])
    assert [plugin.plugin_id() for plugin in plugins] == ["crossref", "openalex"]
