from __future__ import annotations

from typing import Dict, List


def default_resources() -> List[Dict[str, str]]:
    return [
        {"source": "CNIPA", "endpoint": "https://pss-system.cnipa.gov.cn", "kind": "patent"},
        {"source": "WIPO_PATENTSCOPE", "endpoint": "https://patentscope.wipo.int", "kind": "patent"},
        {"source": "EPO_ESPACENET", "endpoint": "https://worldwide.espacenet.com", "kind": "patent"},
        {"source": "USPTO", "endpoint": "https://ppubs.uspto.gov", "kind": "patent"},
        {"source": "GOOGLE_PATENTS", "endpoint": "https://patents.google.com", "kind": "patent"},
        {"source": "GOOGLE_SCHOLAR", "endpoint": "https://scholar.google.com", "kind": "paper"},
        {"source": "SEMANTIC_SCHOLAR", "endpoint": "https://www.semanticscholar.org", "kind": "paper"},
        {"source": "ARXIV", "endpoint": "https://arxiv.org", "kind": "paper"},
        {"source": "IEEE_XPLORE", "endpoint": "https://ieeexplore.ieee.org", "kind": "paper"},
        {"source": "ACM_DL", "endpoint": "https://dl.acm.org", "kind": "paper"},
        {"source": "CNKI", "endpoint": "https://www.cnki.net", "kind": "paper"},
        {"source": "WANFANG", "endpoint": "https://www.wanfangdata.com.cn", "kind": "paper"},
        {"source": "CQVIP", "endpoint": "https://www.cqvip.com", "kind": "paper"},
    ]
