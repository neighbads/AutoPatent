import json

import pytest

from autopatent.config import load_config
from autopatent.pipeline.checkpoint import CheckpointStore


def test_resume_reads_latest_stage(tmp_path):
    ckpt = CheckpointStore(tmp_path / "state")
    ckpt.save(stage_id="STAGE_04", status="done")
    assert ckpt.latest().stage_id == "STAGE_04"


def test_latest_raises_on_malformed_history(tmp_path):
    state = tmp_path / "state"
    ckpt = CheckpointStore(state)
    history_file = state / "checkpoint_history.json"
    history_file.write_text("broken json")
    with pytest.raises(ValueError) as exc:
        ckpt.latest()
    assert str(history_file) in str(exc.value)


def test_latest_raises_on_non_list_history(tmp_path):
    state = tmp_path / "state"
    ckpt = CheckpointStore(state)
    history_file = state / "checkpoint_history.json"
    history_file.write_text(json.dumps({"stage_id": "STAGE_01"}))
    with pytest.raises(ValueError) as exc:
        ckpt.latest()
    assert str(history_file) in str(exc.value)


def test_load_config_raises_on_malformed(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{ invalid json }")
    with pytest.raises(ValueError) as exc:
        load_config(config_path=config_path)
    assert str(config_path) in str(exc.value)


def test_latest_raises_when_entry_missing_keys(tmp_path):
    state = tmp_path / "state"
    ckpt = CheckpointStore(state)
    history_file = state / "checkpoint_history.json"
    history_file.write_text(
        json.dumps(
            [
                {
                    "stage_id": "STAGE_06",
                    "status": "done",
                }
            ]
        )
    )
    with pytest.raises(ValueError) as exc:
        ckpt.latest()
    assert "updated_at" in str(exc.value)


def test_load_config_rejects_checkpoint_root_type(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"checkpoint_root": 123}))
    with pytest.raises(ValueError) as exc:
        load_config(config_path=config_path)
    assert "checkpoint_root" in str(exc.value)


def test_load_config_parses_llm_and_search_provider(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "checkpoint_root": str(tmp_path / "state"),
                "search_provider": "seed-only",
                "llm": {
                    "provider": "openai-compatible",
                    "base_url": "http://127.0.0.1:8000/v1",
                    "api_key_env": "OPENAI_API_KEY",
                    "model": "gpt-5.4",
                    "timeout_sec": 20,
                },
            }
        ),
        encoding="utf-8",
    )
    cfg = load_config(config_path=config_path)
    assert cfg.search_provider == "seed-only"
    assert cfg.llm is not None
    assert cfg.llm.provider == "openai-compatible"
    assert cfg.llm.base_url == "http://127.0.0.1:8000/v1"
    assert cfg.llm.api_key_env == "OPENAI_API_KEY"
    assert cfg.llm.model == "gpt-5.4"
