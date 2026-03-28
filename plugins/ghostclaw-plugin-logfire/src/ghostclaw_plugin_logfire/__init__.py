"""Ghostclaw Logfire Plugin — Analyze Pydantic Logfire observability integration."""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from ghostclaw.core.adapters.metric.base import MetricAdapter
from ghostclaw.core.adapters.base import AdapterMetadata
from ghostclaw.core.adapters.hooks import hookimpl

from .analyzers.config import ConfigAnalyzer
from .analyzers.instrumentation import InstrumentationAnalyzer
from .analyzers.patterns import PatternAnalyzer


class LogfirePlugin(MetricAdapter):
    """Analyzes Python codebases for Pydantic Logfire observability integration."""

    def get_metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            name="logfire",
            version="0.1.0",
            description="Pydantic Logfire observability integration analyzer",
            dependencies=[],
        )

    async def is_available(self) -> bool:
        """Plugin is always available (pure Python analysis)."""
        return True

    async def analyze(
        self,
        root: str,
        files: List[str],
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Analyze the codebase for Logfire integration patterns.

        Args:
            root: Repository root path
            files: List of file paths to analyze
            config: Optional plugin configuration
            **kwargs: Extra arguments from Ghostclaw

        Returns:
            Dict with 'issues', 'architectural_ghosts', 'red_flags'.
        """
        issues: List[Dict[str, Any]] = []
        architectural_ghosts: List[str] = []
        red_flags: List[str] = []

        # Filter to Python files only
        py_files = [f for f in files if f.endswith(".py")]
        if not py_files:
            return {"issues": [], "architectural_ghosts": [], "red_flags": []}

        # Get plugin configuration
        plugin_config = config or {}
        check_config = plugin_config.get("check_config", True)
        check_instrumentation = plugin_config.get("check_instrumentation", True)
        required_integrations = plugin_config.get("required_integrations", [])

        # Run analyzers
        config_analyzer = ConfigAnalyzer(root, py_files)
        instrumentation_analyzer = InstrumentationAnalyzer(root, py_files)
        pattern_analyzer = PatternAnalyzer(root, py_files)

        # 1. Configuration analysis
        if check_config:
            config_results = config_analyzer.analyze()
            issues.extend(config_results.get("issues", []))
            red_flags.extend(config_results.get("red_flags", []))

        # 2. Instrumentation coverage analysis
        if check_instrumentation:
            instr_results = instrumentation_analyzer.analyze()
            issues.extend(instr_results.get("issues", []))
            architectural_ghosts.extend(instr_results.get("architectural_ghosts", []))

        # 3. Pattern analysis (best practices, anti-patterns)
        pattern_results = pattern_analyzer.analyze()
        issues.extend(pattern_results.get("issues", []))
        architectural_ghosts.extend(pattern_results.get("architectural_ghosts", []))

        # 4. Check for required integrations
        if required_integrations:
            for integration in required_integrations:
                found = instrumentation_analyzer.check_integration(integration)
                if not found:
                    issues.append(
                        {
                            "rule_id": "LOGFIRE_MISSING_INTEGRATION",
                            "title": f"Required integration '{integration}' not instrumented",
                            "message": f"The required Logfire integration '{integration}' was not found in the codebase. "
                            f"Add logfire.instrument_{integration}() to enable observability.",
                            "severity": "medium",
                            "file_path": root,
                            "line_start": 0,
                            "line_end": 0,
                            "metadata": {"integration": integration},
                        }
                    )

        return {
            "issues": issues,
            "architectural_ghosts": architectural_ghosts,
            "red_flags": red_flags,
        }

    @hookimpl
    async def ghost_analyze(
        self,
        root: str,
        files: List[str],
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Hook implementation — called by Ghostclaw during analysis."""
        return await self.analyze(root, files, config=config, **kwargs)

    @hookimpl
    def ghost_get_metadata(self) -> Dict[str, Any]:
        """Hook implementation — returns plugin metadata for listing."""
        meta = self.get_metadata()
        return {
            "name": meta.name,
            "version": meta.version,
            "description": meta.description,
            "available": True,
        }
