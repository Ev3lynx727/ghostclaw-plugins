"""Bandit Plugin — integrate Bandit security scanner into Ghostclaw."""

import json
from typing import Dict, List, Any, Optional
from ghostclaw.core.adapters.metric.base import AsyncProcessMetricAdapter
from ghostclaw.core.adapters.base import AdapterMetadata
from ghostclaw.core.adapters.hooks import hookimpl


class BanditPlugin(AsyncProcessMetricAdapter):
    """Runs Bandit on Python files and imports findings into Ghostclaw."""

    def get_metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            name="bandit",
            version="0.1.0",
            description="Bandit Python security scanner integration",
            dependencies=["bandit"]
        )

    async def is_available(self) -> bool:
        """Check if bandit CLI is available."""
        result = await self.run_tool(["bandit", "--version"])
        return result.get("returncode") == 0

    async def analyze(self, root: str, files: List[str], config: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """
        Run Bandit against the repository.

        Args:
            root: Repository root path
            files: List of file paths (ignored, we scan entire root)
            config: Optional dict with 'exclude_paths' and 'severity_threshold'
            **kwargs: Extra arguments sent by the Ghostclaw engine

        Returns:
            Dict with 'issues', 'architectural_ghosts', 'red_flags'.
        """
        # Build bandit command
        cmd = ["bandit", "-r", "-f", "json", "-x", ".ghostclaw/plugins", root]

        if config:
            exclude_paths = config.get("exclude_paths", [])
            if exclude_paths:
                # -x takes comma separated paths
                current_excludes = cmd[cmd.index("-x") + 1]
                cmd[cmd.index("-x") + 1] = f"{current_excludes},{','.join(exclude_paths)}"
                
            threshold = config.get("severity_threshold", "low").lower()
            if threshold == "medium":
                cmd.append("-ll")
            elif threshold in ("high", "critical"):
                cmd.append("-lll")

        result = await self.run_tool(cmd)

        if result.get("returncode") not in (0, 1):
            stderr = result.get("stderr", "")
            if stderr:
                return {
                    "issues": [f"Bandit error: {stderr}"],
                    "architectural_ghosts": [],
                    "red_flags": []
                }
            else:
                return {
                    "issues": [],
                    "architectural_ghosts": [],
                    "red_flags": []
                }

        stdout = result.get("stdout", "")
        if not stdout:
            return {"issues": [], "architectural_ghosts": [], "red_flags": []}

        try:
            bandit_output = json.loads(stdout)
        except json.JSONDecodeError:
            return {
                "issues": ["Failed to parse Bandit JSON output"],
                "architectural_ghosts": [],
                "red_flags": []
            }

        # Normalize findings to Ghostclaw format: list of descriptive strings
        issues = []
        for finding in bandit_output.get("results", []):
            file_path = finding.get("filename", "unknown")
            line = finding.get("line_number", "?")
            test_id = finding.get("test_id", "UNKNOWN")
            severity = finding.get("issue_severity", "?")
            issue_text = finding.get("issue_text", "No description")
            issues.append(f"{file_path}:{line} - {test_id} ({severity}): {issue_text}")

        # Debug print to confirm types
        print(f"[BanditPlugin] Returning {len(issues)} issues; first issue type: {type(issues[0]).__name__ if issues else 'none'}")

        return {
            "issues": issues,
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
