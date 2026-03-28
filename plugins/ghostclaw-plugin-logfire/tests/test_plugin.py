"""Tests for ghostclaw-plugin-logfire."""

import ast
import os
import tempfile
from pathlib import Path

import pytest

from ghostclaw_plugin_logfire import LogfirePlugin
from ghostclaw_plugin_logfire.analyzers.config import (
    ConfigAnalyzer,
    LogfireConfigVisitor,
)
from ghostclaw_plugin_logfire.analyzers.instrumentation import (
    InstrumentationAnalyzer,
    InstrumentationVisitor,
)
from ghostclaw_plugin_logfire.analyzers.patterns import PatternAnalyzer


class TestConfigAnalyzer:
    """Tests for configuration analysis."""

    def test_detects_logfire_import(self):
        """Should detect when logfire is imported."""
        code = "import logfire\n"
        tree = ast.parse(code)
        visitor = LogfireConfigVisitor()
        visitor.visit(tree)
        assert visitor.has_logfire_import is True

    def test_detects_logfire_configure(self):
        """Should detect logfire.configure() calls."""
        code = """
import logfire
logfire.configure()
"""
        tree = ast.parse(code)
        visitor = LogfireConfigVisitor()
        visitor.visit(tree)
        assert visitor.has_configure_call is True

    def test_detects_send_to_logfire_false(self):
        """Should detect local-only mode."""
        code = """
import logfire
logfire.configure(send_to_logfire=False)
"""
        tree = ast.parse(code)
        visitor = LogfireConfigVisitor()
        visitor.visit(tree)
        assert visitor.has_send_to_logfire_false is True

    def test_detects_hardcoded_token(self):
        """Should detect hardcoded tokens (security issue)."""
        code = """
import os
os.environ["LOGFIRE_TOKEN"] = "lgf_abc123def456ghi789"
"""
        tree = ast.parse(code)
        visitor = LogfireConfigVisitor()
        visitor.visit(tree)
        assert len(visitor.hardcoded_tokens) == 1
        assert visitor.hardcoded_tokens[0]["key"] == "LOGFIRE_TOKEN"

    def test_analyzer_finds_unconfigured_import(self):
        """Should flag logfire imported but not configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with import but no configure
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("import logfire\nlogfire.info('hello')\n")

            analyzer = ConfigAnalyzer(tmpdir, [str(test_file)])
            result = analyzer.analyze()

            issues = result["issues"]
            assert any(i["rule_id"] == "LOGFIRE_NOT_CONFIGURED" for i in issues)


class TestInstrumentationAnalyzer:
    """Tests for instrumentation coverage analysis."""

    def test_detects_fastapi_import(self):
        """Should detect FastAPI import."""
        code = "from fastapi import FastAPI\n"
        tree = ast.parse(code)
        visitor = InstrumentationVisitor()
        visitor.visit(tree)
        assert "fastapi" in visitor.imported_packages

    def test_detects_instrument_fastapi(self):
        """Should detect logfire.instrument_fastapi() call."""
        code = """
import logfire
logfire.instrument_fastapi(app)
"""
        tree = ast.parse(code)
        visitor = InstrumentationVisitor()
        visitor.visit(tree)
        assert "fastapi" in visitor.instrumented_calls

    def test_finds_uninstrumented_package(self):
        """Should flag imported but uninstrumented packages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
import logfire
from fastapi import FastAPI
logfire.configure()
# Missing: logfire.instrument_fastapi(app)
""")

            analyzer = InstrumentationAnalyzer(tmpdir, [str(test_file)])
            result = analyzer.analyze()

            issues = result["issues"]
            assert any(
                i["rule_id"] == "LOGFIRE_UNINSTRUMENTED_PACKAGE"
                and i["metadata"]["package"] == "fastapi"
                for i in issues
            )

    def test_check_integration_found(self):
        """Should return True when integration is instrumented."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
import logfire
logfire.instrument_fastapi(app)
""")

            analyzer = InstrumentationAnalyzer(tmpdir, [str(test_file)])
            assert analyzer.check_integration("fastapi") is True

    def test_check_integration_not_found(self):
        """Should return False when integration is not instrumented."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
import logfire
logfire.configure()
""")

            analyzer = InstrumentationAnalyzer(tmpdir, [str(test_file)])
            assert analyzer.check_integration("fastapi") is False


class TestPatternAnalyzer:
    """Tests for pattern analysis."""

    def test_detects_empty_span_name(self):
        """Should flag empty span names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
import logfire
with logfire.span(""):
    pass
""")

            analyzer = PatternAnalyzer(tmpdir, [str(test_file)])
            result = analyzer.analyze()

            issues = result["issues"]
            assert any(i["rule_id"] == "LOGFIRE_EMPTY_SPAN_NAME" for i in issues)

    def test_architectural_ghost_no_exception_handling(self):
        """Should flag spans without exception handling."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
import logfire

def process_data():
    with logfire.span("process"):
        do_something()

def do_something():
    pass
""")

            analyzer = PatternAnalyzer(tmpdir, [str(test_file)])
            result = analyzer.analyze()

            ghosts = result["architectural_ghosts"]
            assert len(ghosts) > 0
            assert "record exceptions" in ghosts[0].lower()


class TestLogfirePlugin:
    """Integration tests for the full plugin."""

    @pytest.mark.asyncio
    async def test_metadata(self):
        """Should return correct metadata."""
        plugin = LogfirePlugin()
        meta = plugin.get_metadata()
        assert meta.name == "logfire"
        assert meta.version == "0.1.0"

    @pytest.mark.asyncio
    async def test_is_available(self):
        """Plugin should always be available."""
        plugin = LogfirePlugin()
        assert await plugin.is_available() is True

    @pytest.mark.asyncio
    async def test_analyze_empty_dir(self):
        """Should handle empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin = LogfirePlugin()
            result = await plugin.analyze(tmpdir, [])
            assert result == {"issues": [], "architectural_ghosts": [], "red_flags": []}

    @pytest.mark.asyncio
    async def test_analyze_non_python_files(self):
        """Should skip non-Python files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.js"
            test_file.write_text("console.log('hello');")

            plugin = LogfirePlugin()
            result = await plugin.analyze(tmpdir, [str(test_file)])
            assert result == {"issues": [], "architectural_ghosts": [], "red_flags": []}

    @pytest.mark.asyncio
    async def test_analyze_properly_configured(self):
        """Should return no issues for properly configured project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "main.py"
            test_file.write_text("""
import logfire
from fastapi import FastAPI

logfire.configure()
app = FastAPI()
logfire.instrument_fastapi(app)

@app.get("/")
def root():
    with logfire.span("handle_request"):
        return {"hello": "world"}
""")

            plugin = LogfirePlugin()
            result = await plugin.analyze(tmpdir, [str(test_file)])

            # Should have no high/critical issues
            high_issues = [
                i for i in result["issues"] if i["severity"] in ("high", "critical")
            ]
            assert len(high_issues) == 0

    @pytest.mark.asyncio
    async def test_analyze_missing_configuration(self):
        """Should detect missing configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "app.py"
            test_file.write_text("""
import logfire
from fastapi import FastAPI

app = FastAPI()
# Missing: logfire.configure()
""")

            plugin = LogfirePlugin()
            result = await plugin.analyze(tmpdir, [str(test_file)])

            assert any(
                i["rule_id"] == "LOGFIRE_NOT_CONFIGURED" for i in result["issues"]
            )

    @pytest.mark.asyncio
    async def test_ghost_get_metadata_hook(self):
        """Should return metadata via hook."""
        plugin = LogfirePlugin()
        meta = plugin.ghost_get_metadata()
        assert meta["name"] == "logfire"
        assert meta["available"] is True
