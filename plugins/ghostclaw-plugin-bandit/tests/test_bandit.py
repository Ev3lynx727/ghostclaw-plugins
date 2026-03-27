"""Tests for ghostclaw-plugin-bandit."""

import json
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from ghostclaw_plugin_bandit import BanditPlugin


def test_bandit_plugin_initialization():
    plugin = BanditPlugin()
    meta = plugin.get_metadata()
    assert meta.name == "bandit"
    assert meta.version == "0.1.0"


@pytest.mark.asyncio
async def test_bandit_analyze_success(tmp_path):
    # Create a dummy Python file to scan
    sample = tmp_path / "sample.py"
    sample.write_text("import pickle\npickle.loads(data)")  # should trigger B301

    plugin = BanditPlugin()

    # Mock run_tool to return sample Bandit JSON output
    mock_output = {
        "returncode": 1,  # bandit returns 1 when issues found
        "stdout": json.dumps({
            "results": [
                {
                    "filename": str(sample),
                    "line_number": 1,
                    "issue_severity": "HIGH",
                    "issue_confidence": "HIGH",
                    "test_id": "B301",
                    "test_name": "pickle",
                    "issue_text": "Possible insecure usage of pickle",
                    "line_range": [1]
                }
            ]
        }),
        "stderr": ""
    }

    with patch.object(plugin, "run_tool", new_callable=AsyncMock, return_value=mock_output):
        findings = await plugin.analyze(str(tmp_path), [])

    assert "issues" in findings
    assert len(findings["issues"]) == 1
    assert findings["issues"][0]["test_id"] == "B301"


@pytest.mark.asyncio
async def test_bandit_analyze_timeout():
    plugin = BanditPlugin()

    with patch.object(plugin, "run_tool", side_effect=asyncio.TimeoutError()):
        findings = await plugin.analyze("/some/path", [])

    assert len(findings["issues"]) == 1
    assert "timed out" in findings["issues"][0].lower()


def test_bandit_metadata_hook():
    plugin = BanditPlugin()
    meta = plugin.ghost_get_metadata()
    assert meta["name"] == "bandit"
    assert meta["version"] == "0.1.0"
    assert "available" in meta
