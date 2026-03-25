from __future__ import annotations

import json

from autopatent.pipeline import StageContext
from autopatent.pipeline.stages.stage_00_input_ingest import InputIngestStage


def test_input_ingest_writes_doc_digest_and_code_inventory(tmp_path):
    doc_path = tmp_path / "seed.md"
    doc_path.write_text(
        "# 技术草稿\n\n本方案涉及 IKEv2 与 TLCP 的混合协商机制。\n",
        encoding="utf-8",
    )
    code_dir = tmp_path / "swssl"
    code_dir.mkdir()
    (code_dir / "tlcp_adapter.c").write_text("int main(void){return 0;}\n", encoding="utf-8")
    (code_dir / "README.txt").write_text("notes\n", encoding="utf-8")

    ctx = StageContext(
        work_dir=tmp_path,
        metadata={"topic": "混合抗量子方案", "input_doc": str(doc_path), "code_dir": str(code_dir)},
    )
    stage = InputIngestStage()
    result = stage.run(ctx)

    digest_path = tmp_path / "artifacts" / "input_doc_digest.md"
    inventory_path = tmp_path / "artifacts" / "code_inventory.json"

    assert digest_path.exists()
    assert inventory_path.exists()
    assert "input_doc_digest_path" in result.outputs
    assert "code_inventory_path" in result.outputs

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    files = inventory["files"]
    assert any("tlcp_adapter.c" in item["path"] for item in files)
