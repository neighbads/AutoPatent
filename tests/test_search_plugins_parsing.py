from __future__ import annotations

import json

from autopatent.search.plugins.arxiv_plugin import ArxivPlugin
from autopatent.search.plugins.base import RequestSpec
from autopatent.search.plugins.crossref_plugin import CrossrefPlugin
from autopatent.search.plugins.epo_ops_plugin import EpoOpsPlugin
from autopatent.search.plugins.openalex_plugin import OpenAlexPlugin
from autopatent.search.plugins.semantic_scholar_plugin import SemanticScholarPlugin


def test_openalex_plugin_parses_response_fixture():
    plugin = OpenAlexPlugin()
    payload = json.dumps(
        {
            "results": [
                {
                    "title": "Hybrid Post-Quantum TLS",
                    "publication_year": 2024,
                    "doi": "https://doi.org/10.1234/example",
                    "id": "https://openalex.org/W1",
                }
            ]
        }
    )
    rows = plugin.parse_response(payload, RequestSpec(method="GET", url="https://api.openalex.org/works"))
    assert len(rows) == 1
    assert rows[0]["plugin_id"] == "openalex"
    assert rows[0]["title"] == "Hybrid Post-Quantum TLS"


def test_arxiv_plugin_parses_atom_fixture():
    plugin = ArxivPlugin()
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <published>2024-01-01T00:00:00Z</published>
    <title>Post-Quantum Certificate Handshake</title>
    <summary>Summary text.</summary>
    <author><name>Alice</name></author>
  </entry>
</feed>"""
    rows = plugin.parse_response(xml, RequestSpec(method="GET", url="http://export.arxiv.org/api/query"))
    assert len(rows) == 1
    assert rows[0]["plugin_id"] == "arxiv"
    assert rows[0]["year"] == 2024


def test_semantic_scholar_plugin_parses_items_fixture():
    plugin = SemanticScholarPlugin()
    payload = json.dumps(
        {
            "data": [
                {
                    "title": "Quantum-safe certificate chain",
                    "year": 2025,
                    "url": "https://www.semanticscholar.org/paper/abc",
                    "authors": [{"name": "Bob"}],
                    "externalIds": {"DOI": "10.1000/abc"},
                }
            ]
        }
    )
    rows = plugin.parse_response(payload, RequestSpec(method="GET", url="https://api.semanticscholar.org"))
    assert len(rows) == 1
    assert rows[0]["plugin_id"] == "semantic_scholar"
    assert rows[0]["doi"] == "10.1000/abc"


def test_crossref_plugin_parses_items_fixture():
    plugin = CrossrefPlugin()
    payload = json.dumps(
        {
            "message": {
                "items": [
                    {
                        "title": ["TLS Hybrid Key Exchange"],
                        "DOI": "10.5555/tls-hybrid",
                        "URL": "https://doi.org/10.5555/tls-hybrid",
                        "issued": {"date-parts": [[2023, 6, 1]]},
                    }
                ]
            }
        }
    )
    rows = plugin.parse_response(payload, RequestSpec(method="GET", url="https://api.crossref.org/works"))
    assert len(rows) == 1
    assert rows[0]["plugin_id"] == "crossref"
    assert rows[0]["year"] == 2023


def test_epo_plugin_skips_without_credentials(monkeypatch):
    monkeypatch.delenv("EPO_OPS_CONSUMER_KEY", raising=False)
    monkeypatch.delenv("EPO_OPS_CONSUMER_SECRET", raising=False)
    plugin = EpoOpsPlugin()
    assert plugin.supports("quantum ipsec", "topic") is False
    assert plugin.build_requests("quantum ipsec", "topic", limit=3) == []
