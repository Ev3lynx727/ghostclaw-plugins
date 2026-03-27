"""Tests for ghostclaw-plugin-template."""

import pytest
from ghostclaw_plugin_template import TemplatePlugin


def test_plugin_initialization():
    plugin = TemplatePlugin()
    meta = plugin.get_metadata()
    assert meta.name == "template"
    assert meta.version == "0.1.0"


@pytest.mark.asyncio
async def test_plugin_analyze(tmp_path):
    plugin = TemplatePlugin()
    findings = await plugin.analyze(str(tmp_path), [])
    assert "issues" in findings
    assert isinstance(findings["issues"], list)
    assert "architectural_ghosts" in findings
    assert "red_flags" in findings


def test_plugin_metadata_hook():
    plugin = TemplatePlugin()
    meta = plugin.ghost_get_metadata()
    assert meta["name"] == "template"
    assert meta["version"] == "0.1.0"
