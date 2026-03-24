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
