"""
Minimal Ghostclaw plugin for testing orchestrator integration.

This plugin demonstrates the basic structure and can be used to validate
that orchestrator routing works correctly.
"""

from typing import Any, Dict
from ghostclaw.core.adapters.base import AdapterMetadata, MetricAdapter
from ghostclaw.core.adapters.hooks import GhostclawPluginSpecs


class DemoPlugin(MetricAdapter):
    """A minimal plugin that returns a trivial issue for testing."""

    def get_metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            name="demo",
            version="0.1.0",
            description="Minimal test plugin for orchestrator validation",
            author="Test",
        )

    async def is_available(self) -> bool:
        return True

    async def analyze(self, root: str, files: list[str]) -> dict[str, Any]:
        """Return a simple issue for each Python file found."""
        issues = []
        for f in files:
            if f.endswith(".py"):
                issues.append({
                    "file": f,
                    "line": 1,
                    "col": 0,
                    "type": "demo_issue",
                    "message": f"Demo plugin analyzing {f}",
                    "severity": "info"
                })
        return {
            "issues": issues,
            "architectural_ghosts": [],
            "red_flags": [f"Demo plugin processed {len(issues)} files"],
            "metadata": {"plugin": "demo", "files_analyzed": len(files)}
        }


class OrchestratorDemoPlugin:
    """Plugin entry point for Ghostclaw."""

    def __init__(self):
        self.adapter = DemoPlugin()

    def get_metadata(self):
        return self.adapter.get_metadata()

    async def is_available(self) -> bool:
        return True

    async def ghost_analyze(self, root: str, files: list[str]) -> dict[str, Any]:
        return await self.adapter.analyze(root, files)
