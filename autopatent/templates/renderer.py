from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


DEFAULT_TEMPLATE_NAME = "cn_invention_default"


@dataclass(frozen=True)
class RenderedDisclosure:
    template_name: str
    markdown: str
    docx_markdown: str


_PLACEHOLDER_RE = re.compile(r"{{\s*([A-Za-z0-9_\\.]+)\s*}}")


def _resolve_path(context: Mapping[str, Any], path: str) -> Any:
    current: Any = context
    for part in path.split("."):
        if isinstance(current, Mapping):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
        if current is None:
            return ""
    return current


def _render_text(template_text: str, context: Mapping[str, Any]) -> str:
    def _replace(match: re.Match[str]) -> str:
        value = _resolve_path(context, match.group(1))
        return "" if value is None else str(value)

    return _PLACEHOLDER_RE.sub(_replace, template_text)


def _defaults_dir() -> Path:
    return Path(__file__).resolve().parent / "defaults"


def render_disclosure(*, context: Mapping[str, Any], template_name: str | None) -> RenderedDisclosure:
    user_template = template_name
    selected_template = user_template or DEFAULT_TEMPLATE_NAME

    defaults = _defaults_dir()
    markdown_path = defaults / f"{selected_template}.md.j2"
    docx_markdown_path = defaults / f"{selected_template}.docx.j2.md"

    markdown_template = markdown_path.read_text(encoding="utf-8")
    docx_markdown_template = docx_markdown_path.read_text(encoding="utf-8")

    return RenderedDisclosure(
        template_name=selected_template,
        markdown=_render_text(markdown_template, context),
        docx_markdown=_render_text(docx_markdown_template, context),
    )

