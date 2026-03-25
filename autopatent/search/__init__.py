"""Search helpers for CN MVP prior-art scanning."""

from autopatent.search.dedup import deduplicate_hits, normalize_title
from autopatent.search.evidence_summary import summarize_hits
from autopatent.search.query_builder import build_queries
from autopatent.search.resources import default_resources

__all__ = [
    "build_queries",
    "default_resources",
    "deduplicate_hits",
    "normalize_title",
    "summarize_hits",
]
