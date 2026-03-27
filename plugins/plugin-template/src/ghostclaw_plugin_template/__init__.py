"""Ghostclaw Plugin Template — Minimal Working Example.

Replace this with your actual plugin logic.
"""

from typing import Dict, List, Any, Optional
from ghostclaw.core.adapters.metric.base import AsyncProcessMetricAdapter
from ghostclaw.core.adapters.base import AdapterMetadata
from ghostclaw.core.adapters.hooks import hookimpl


class TemplatePlugin(AsyncProcessMetricAdapter):
    """Example plugin that does nothing (yet). Inherit from AsyncProcessMetricAdapter for subprocess-based tools."""

    def get_metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            name="template",
            version="0.1.0",
            description="Template plugin — replace with real logic",
            dependencies=[]
        )

    async def is_available(self) -> bool:
        """Check if external dependency is available. Override in subclass."""
        return True

    async def analyze(self, root: str, files: List[str], config: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """
        Implement your analysis here.

        Args:
            root: Repository root path
            files: List of file paths to analyze
            config: Optional dictionary containing user configurations for this plugin
            **kwargs: Extra arguments passed by Ghostclaw (like environment flags)

        Returns:
            Dict with 'issues', 'architectural_ghosts', 'red_flags' keys.
        """
        # Example of config usage:
        # my_setting = config.get("my_setting", "default_value") if config else "default_value"

        return {
            "issues": [],
            "architectural_ghosts": [],
            "red_flags": []
        }

    @hookimpl
    async def ghost_analyze(self, root: str, files: List[str], config: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
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
            "available": True
        }