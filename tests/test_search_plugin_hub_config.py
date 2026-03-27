from __future__ import annotations

import json

import pytest

from autopatent.config import load_config


def test_load_config_parses_plugin_hub_defaults(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({}), encoding="utf-8")

    cfg = load_config(config_path=config_path)
    assert cfg.search.plugin_hub.max_workers == 8
    assert cfg.search.plugin_hub.request_timeout_sec == 20
    assert cfg.search.plugin_hub.retry.max_attempts == 3
    assert cfg.search.plugin_hub.fallback_chain == ["jina_reader", "crawl4ai"]


def test_load_config_rejects_unknown_plugin_id(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "search": {
                    "plugin_hub": {
                        "enabled_plugins": ["openalex", "not-exist"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as exc:
        load_config(config_path=config_path)
    assert "unknown plugin ids" in str(exc.value)


def test_load_config_rejects_unknown_fallback_runner(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "search": {
                    "plugin_hub": {
                        "fallback_chain": ["jina_reader", "custom_runner"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as exc:
        load_config(config_path=config_path)
    assert "unsupported runners" in str(exc.value)
