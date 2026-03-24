from __future__ import annotations


def test_disclosure_render_populates_all_placeholders() -> None:
    from autopatent.templates.renderer import render_disclosure

    context = {
        "title": "Flux Capacitor Cooling System",
        "technical_field": "Thermal management for electronics",
        "background": "Existing cooling solutions are bulky.",
        "summary": "A compact cooling system using microchannels.",
        "embodiments": "One embodiment uses copper microchannels.",
    }

    rendered = render_disclosure(context=context, template_name="cn_invention_default")

    assert rendered.template_name == "cn_invention_default"
    assert "Flux Capacitor Cooling System" in rendered.markdown
    assert "Flux Capacitor Cooling System" in rendered.docx_markdown
    assert "{{" not in rendered.markdown
    assert "{{" not in rendered.docx_markdown

