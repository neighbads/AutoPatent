import pytest

from autopatent.pipeline.checkpoint import CheckpointStore


def test_resume_reads_latest_stage(tmp_path):
    ckpt = CheckpointStore(tmp_path / "state")
    ckpt.save(stage_id="STAGE_04", status="done")
    assert ckpt.latest().stage_id == "STAGE_04"
