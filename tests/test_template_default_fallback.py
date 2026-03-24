from __future__ import annotations


def test_default_template_used_when_not_specified() -> None:
    # Import inside the test so the failure mode is explicit during the RED run.
    from autopatent.templates.renderer import render_disclosure

    context = {
        "title": "Example Invention Title",
        "technical_field": "Example technical field",
        "background": "Example background",
        "summary": "Example summary",
        "embodiments": "Example embodiments",
    }

    rendered = render_disclosure(context=context, template_name=None)

    assert rendered.template_name == "cn_invention_default"
    assert "Example Invention Title" in rendered.markdown
    assert "Example Invention Title" in rendered.docx_markdown

