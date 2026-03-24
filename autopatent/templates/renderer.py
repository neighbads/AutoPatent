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


_PLACEHOLDER_RE = re.compile(r"{{\s*([A-Za-z0-9_.]+)\s*}}")
_TEMPLATE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _resolve_path(context: Mapping[str, Any], path: str) -> Any:
    current: Any = context
    for part in path.split("."):
        if isinstance(current, Mapping):
            if part not in current:
                raise KeyError(path)
            current = current[part]
        else:
            if not hasattr(current, part):
                raise KeyError(path)
            current = getattr(current, part)
        if current is None:
            raise KeyError(path)
    return current


def _render_text(template_text: str, context: Mapping[str, Any]) -> str:
    if "{%" in template_text or "%}" in template_text:
        raise ValueError("Unsupported Jinja block syntax: {% ... %}")

    def _replace(match: re.Match[str]) -> str:
        placeholder = match.group(1)
        try:
            value = _resolve_path(context, placeholder)
        except KeyError as exc:
            raise ValueError(f"Missing required template value: {placeholder}") from exc
        return str(value)

    return _PLACEHOLDER_RE.sub(_replace, template_text)


def _defaults_dir() -> Path:
    return Path(__file__).resolve().parent / "defaults"


def _validate_template_name(name: str) -> None:
    if not _TEMPLATE_NAME_RE.fullmatch(name):
        raise ValueError(f"Invalid template name: {name}")


def _load_template_pair(defaults: Path, selected_template: str) -> tuple[str, str, str]:
    markdown_path = defaults / f"{selected_template}.md.j2"
    docx_markdown_path = defaults / f"{selected_template}.docx.j2.md"
    if not markdown_path.is_file() or not docx_markdown_path.is_file():
        if selected_template != DEFAULT_TEMPLATE_NAME:
            selected_template = DEFAULT_TEMPLATE_NAME
            markdown_path = defaults / f"{selected_template}.md.j2"
            docx_markdown_path = defaults / f"{selected_template}.docx.j2.md"
        if not markdown_path.is_file() or not docx_markdown_path.is_file():
            raise FileNotFoundError(f"Template files not found for: {selected_template}")
    return (
        selected_template,
        markdown_path.read_text(encoding="utf-8"),
        docx_markdown_path.read_text(encoding="utf-8"),
    )


def render_disclosure(
    *, context: Mapping[str, Any], template_name: str | None = None
) -> RenderedDisclosure:
    user_template = template_name
    selected_template = user_template or DEFAULT_TEMPLATE_NAME
    _validate_template_name(selected_template)

    defaults = _defaults_dir()
    selected_template, markdown_template, docx_markdown_template = _load_template_pair(
        defaults, selected_template
    )

    return RenderedDisclosure(
        template_name=selected_template,
        markdown=_render_text(markdown_template, context),
        docx_markdown=_render_text(docx_markdown_template, context),
    )
