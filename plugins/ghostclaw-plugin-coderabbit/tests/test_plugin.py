"""Tests for ghostclaw-plugin-coderabbit."""

import pytest
from ghostclaw_plugin_coderabit.plugin import CustomAdapter


def test_plugin_initialization():
    plugin = CustomAdapter()
    meta = plugin.get_metadata()
    assert meta.name == "coderabbit"
    assert meta.version == "0.1.0"


@pytest.mark.asyncio
async def test_plugin_analyze(tmp_path):
    plugin = CustomAdapter()
    findings = await plugin.analyze(str(tmp_path), [])
    assert "issues" in findings
    assert isinstance(findings["issues"], list)
    assert "architectural_ghosts" in findings
    assert "red_flags" in findings


def test_plugin_metadata_hook():
    plugin = CustomAdapter()
    meta = plugin.ghost_get_metadata()
    assert meta["name"] == "coderabbit"
    assert meta["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_plugin_is_available():
    plugin = CustomAdapter()
    # Should return False if coderabbit not installed
    available = await plugin.is_available()
    assert isinstance(available, bool)
