"""Tests for ghostclaw-plugin-template."""

import pytest
from ghostclaw_plugin_template import TemplatePlugin


def test_plugin_initialization():
    plugin = TemplatePlugin()
    assert plugin.name == "template"
    assert plugin.version == "0.1.0"


def test_plugin_analyze(tmp_path):
    plugin = TemplatePlugin()
    findings = plugin.analyze(str(tmp_path), {})
    assert "plugin" in findings
    assert findings["plugin"] == "template"
    assert "issues" in findings
    assert isinstance(findings["issues"], list)


def test_plugin_report():
    plugin = TemplatePlugin()
    raw_findings = {"issues": []}
    report = plugin.report(raw_findings)
    assert "metadata" in report
    assert report["metadata"]["plugin"] == "template"
