from __future__ import annotations

import pytest


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


def test_disclosure_render_falls_back_when_template_missing() -> None:
    from autopatent.templates.renderer import render_disclosure

    context = {
        "title": "Fallback Title",
        "technical_field": "Field",
        "background": "Background",
        "summary": "Summary",
        "embodiments": "Embodiments",
    }
    rendered = render_disclosure(context=context, template_name="does_not_exist")
    assert rendered.template_name == "cn_invention_default"
    assert "Fallback Title" in rendered.markdown


def test_disclosure_render_raises_on_missing_placeholder_value() -> None:
    from autopatent.templates.renderer import render_disclosure

    context = {
        "title": "Missing Field Title",
        "technical_field": "Field",
        "summary": "Summary",
        "embodiments": "Embodiments",
    }
    with pytest.raises(ValueError):
        render_disclosure(context=context, template_name="cn_invention_default")


def test_disclosure_render_raises_on_unrendered_placeholder(monkeypatch) -> None:
    from autopatent.templates import renderer as disclosure_renderer

    def fake_load_template_pair(_defaults, _selected):
        return (
            "cn_invention_default",
            "# Title\n{{ title }}\n{{ invalid-placeholder }}",
            "# Title\n{{ title }}",
        )

    monkeypatch.setattr(disclosure_renderer, "_load_template_pair", fake_load_template_pair)

    context = {
        "title": "Safe Title",
        "technical_field": "Field",
        "background": "Background",
        "summary": "Summary",
        "embodiments": "Embodiments",
    }
    with pytest.raises(ValueError):
        disclosure_renderer.render_disclosure(context=context, template_name=None)


def test_disclosure_render_allows_literal_braces_in_context_values() -> None:
    from autopatent.templates.renderer import render_disclosure

    context = {
        "title": "Literal {{ braces }} title",
        "technical_field": "Field",
        "background": "Background",
        "summary": "Summary",
        "embodiments": "Embodiments",
    }
    rendered = render_disclosure(context=context, template_name="cn_invention_default")
    assert "Literal {{ braces }} title" in rendered.markdown



def test_sansec_disclosure_template_renders_with_appendix() -> None:
    from autopatent.templates.renderer import render_disclosure

    context = {
        "title": "Sansec Search Report for Quantum Firewall",
        "technical_field": "Post-quantum communication security",
        "background": "Legacy IPSec stacks fall short against quantum threats.",
        "summary": "A hybrid TLCP/IPSec architecture that resists lattice attacks.",
        "embodiments": "Combines AES-256 tunnels with adaptive telemetry.",
        "embodiments_detail": "Routing stacks include multi-path resilience and failover logic.",
        "invention_title": "Quantum-Resistant VPN System",
        "technical_field_cn": "后量子通信安全",
        "background_art": "RSA-based handshakes are no longer sufficient in the quantum era.",
        "core_solution": "Integrate TLCP with lattice KEM and zero-trust routing policies.",
        "technical_effects": "Handshake hardening and entropy amplification for every packet.",
        "evidence_refs_text": "- e1\n- e2",
        "claim_seed_points_text": "- claim 1\n- claim 2",
        "code_evidence_text": "- code/routing.c",
    }

    rendered = render_disclosure(context=context, template_name="sansec_disclosure_v1")

    assert "附录A 检索报告要点" in rendered.markdown
    assert "{{" not in rendered.markdown
