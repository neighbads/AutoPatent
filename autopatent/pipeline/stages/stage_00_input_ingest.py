from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from autopatent.pipeline import StageContext, StageResult


@dataclass
class InputIngestStage:
    """Stage 00: Normalize user inputs into ctx.metadata.

    Minimal behavior:
    - If `topic` exists, keep it.
    - If `input_doc` exists and is a Path/str, persist its string form.
    """

    stage_id: str = "STAGE_00"
    requires: list[str] = field(default_factory=list)
    produces: list[str] = field(
        default_factory=lambda: [
            "topic",
            "input_doc",
            "code_dir",
            "input_doc_digest_path",
            "code_inventory_path",
        ]
    )

    def run(self, ctx: StageContext) -> StageResult:
        topic = ctx.metadata.get("topic")
        if topic is not None and not isinstance(topic, str):
            ctx.metadata["topic"] = str(topic)

        input_doc: Optional[Any] = ctx.metadata.get("input_doc")
        if isinstance(input_doc, Path):
            ctx.metadata["input_doc"] = str(input_doc)
        elif input_doc is not None and not isinstance(input_doc, str):
            ctx.metadata["input_doc"] = str(input_doc)

        code_dir: Optional[Any] = ctx.metadata.get("code_dir")
        if isinstance(code_dir, Path):
            ctx.metadata["code_dir"] = str(code_dir)
        elif code_dir is not None and not isinstance(code_dir, str):
            ctx.metadata["code_dir"] = str(code_dir)

        digest_path = _write_input_doc_digest(ctx)
        if digest_path is not None:
            ctx.metadata["input_doc_digest_path"] = str(digest_path)

        inventory_path = _write_code_inventory(ctx)
        if inventory_path is not None:
            ctx.metadata["code_inventory_path"] = str(inventory_path)

        result = StageResult(produces=list(self.produces))
        result.outputs = {k: ctx.metadata.get(k) for k in self.produces}
        return result


def _write_input_doc_digest(ctx: StageContext) -> Optional[Path]:
    raw = str(ctx.metadata.get("input_doc") or "").strip()
    if not raw:
        return None
    doc_path = Path(raw).expanduser()
    if not doc_path.is_absolute():
        doc_path = (ctx.work_dir / doc_path).resolve()
    else:
        doc_path = doc_path.resolve()
    if not doc_path.exists() or not doc_path.is_file():
        return None

    content = doc_path.read_text(encoding="utf-8", errors="ignore")
    non_empty = [line.strip() for line in content.splitlines() if line.strip()]
    digest_lines = non_empty[:20]

    out = ctx.work_dir / "artifacts" / "input_doc_digest.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(digest_lines) + ("\n" if digest_lines else ""), encoding="utf-8")
    return out


def _write_code_inventory(ctx: StageContext) -> Optional[Path]:
    raw = str(ctx.metadata.get("code_dir") or "").strip()
    if not raw:
        return None
    code_root = Path(raw).expanduser()
    if not code_root.is_absolute():
        code_root = (ctx.work_dir / code_root).resolve()
    else:
        code_root = code_root.resolve()
    if not code_root.exists() or not code_root.is_dir():
        return None

    files = _collect_source_files(code_root)
    payload: Dict[str, Any] = {
        "root": str(code_root),
        "file_count": len(files),
        "files": files,
    }
    out = ctx.work_dir / "artifacts" / "code_inventory.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _collect_source_files(root: Path) -> List[Dict[str, str]]:
    allowed_exts = {
        ".c",
        ".cc",
        ".cpp",
        ".h",
        ".hpp",
        ".py",
        ".go",
        ".rs",
        ".java",
        ".js",
        ".ts",
        ".md",
    }
    entries: List[Dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext not in allowed_exts:
            continue
        rel = path.relative_to(root)
        entries.append({"path": str(rel), "ext": ext})
        if len(entries) >= 300:
            break
    return entries
