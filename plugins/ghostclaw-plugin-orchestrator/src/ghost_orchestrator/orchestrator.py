"""Main orchestrator: coordinates plugin selection and execution."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

from .llm_planner import LLMPlanner
from .models import (
    AnalysisPlan,
    OrchestratorConfig,
    PluginCapability,
    RepositoryProfile,
)
from .vector_advisor import VectorAdvisor

logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates intelligent plugin selection and execution."""

    def __init__(
        self,
        config: OrchestratorConfig,
        plugin_capabilities: dict[str, PluginCapability],
        available_plugins: list[str],
        qmd_store=None,
        llm_client=None,  # optional pre-configured LLM client
        repo_profile: Optional[RepositoryProfile] = None,
        repo_path: Optional[str] = None,
    ):
        """
        Args:
            config: Orchestrator configuration
            plugin_capabilities: Map of plugin name → PluginCapability
            available_plugins: List of plugin names that can be executed
            qmd_store: Optional QMDMemoryStore for vector search
            llm_client: Optional LLM client instance
                (if None, LLMPlanner will create)
            repo_profile: Pre-computed repository profile
                (or will be extracted from repo_path)
            repo_path: Path to repository (required if repo_profile not provided)
        """
        self.config = config
        self.plugin_capabilities = plugin_capabilities
        self.available_plugins = available_plugins
        self.qmd_store = qmd_store

        # Initialize advisors
        self.vector_advisor = VectorAdvisor(
            qmd_store=qmd_store,
            plugin_capabilities=plugin_capabilities,
            config=config,
        )

        # Initialize LLM planner if enabled and model available
        self.llm_planner = None
        if config.use_llm:
            model_name = config.llm_model or "openrouter/anthropic/claude-3-sonnet"
            self.llm_planner = LLMPlanner(
                model_name=model_name,
                plugin_capabilities=plugin_capabilities,
                config=config,
            )

        # Repository profile
        if repo_profile:
            self.repo_profile = repo_profile
        elif repo_path:
            self.repo_profile = self._extract_profile(repo_path)
        else:
            raise ValueError("Must provide either repo_profile or repo_path")

    def _extract_profile(self, repo_path: str) -> RepositoryProfile:
        """Extract repository features."""
        path = Path(repo_path)
        profile = RepositoryProfile(path=str(path.absolute()))

        # TODO: Implement actual extraction
        # - Count lines per language (using pygments or git ls-files)
        # - Detect frameworks (from dependency files: requirements.txt,
        #   package.json, etc.)
        # - Git status
        # - File patterns

        # For now, return a minimal placeholder
        logger.warning("_extract_profile is a stub — needs implementation")
        profile.total_lines = 0
        profile.languages = {}
        profile.frameworks = []

        return profile

    async def plan(self, force_llm: bool = False) -> AnalysisPlan:
        """
        Generate an analysis plan.

        Args:
            force_llm: If True, use LLM even if vector advisor is available

        Returns:
            AnalysisPlan with ordered plugins and rationale
        """
        logger.info("Generating analysis plan...")

        # Step 1: Get vector-based recommendations (always available)
        vector_recs = await self.vector_advisor.recommend(
            self.repo_profile, self.available_plugins
        )

        # Step 2: Optionally augment with LLM planning
        if force_llm and self.llm_planner:
            logger.info("Using LLM planner...")
            llm_plan = await self.llm_planner.plan(
                self.repo_profile, self.available_plugins
            )

            if llm_plan.plugins and llm_plan.confidence > 0.5:
                # Merge or replace? For now, use LLM as primary if confidence high
                logger.info(
                    "LLM plan selected %d plugins",
                    len(llm_plan.plugins),
                )
                return llm_plan
            else:
                logger.warning(
                    "LLM plan low confidence, falling back to vector advisor"
                )

        # Step 3: Build plan from vector recommendations
        selected_plugins = []
        rationales = []

        for plugin_name, score, reason in vector_recs:
            if len(selected_plugins) >= self.config.max_plugins:
                break
            selected_plugins.append(plugin_name)
            rationales.append(f"[score={score:.2f}] {reason}")

        confidence = (
            sum(score for _, score, _ in vector_recs[: len(selected_plugins)])
            / max(len(selected_plugins), 1)
        )

        return AnalysisPlan(
            plugins=selected_plugins,
            rationale=rationales,
            confidence=confidence,
            metadata={
                "source": "vector_advisor",
                "vector_weight": self.config.vector_weight,
                "heuristics_weight": self.config.heuristics_weight,
                "repo_profile": {
                    "languages": self.repo_profile.languages,
                    "total_lines": self.repo_profile.total_lines,
                },
            },
        )

    async def execute_plan(
        self,
        plan: AnalysisPlan,
        plugin_executor,  # async function that runs a plugin and returns results
    ) -> dict[str, Any]:
        """
        Execute the analysis plan with controlled concurrency.

        Args:
            plan: AnalysisPlan to execute
            plugin_executor: Async callable that takes plugin name
                and returns results dict

        Returns:
            Aggregated results from all plugins
        """
        logger.info(
            "Executing plan with %d plugins (max_concurrent=%d)",
            len(plan.plugins),
            self.config.max_concurrent_plugins,
        )

        semaphore = asyncio.Semaphore(self.config.max_concurrent_plugins)

        async def run_plugin(plugin_name: str) -> dict[str, Any]:
            async with semaphore:
                logger.info(f"Running plugin: {plugin_name}")
                try:
                    return await plugin_executor(plugin_name)
                except Exception as e:
                    logger.error(f"Plugin {plugin_name} failed: {e}")
                    return {
                        "issues": [],
                        "architectural_ghosts": [],
                        "red_flags": [f"Plugin error: {plugin_name} — {e}"],
                    }

        # Create tasks
        tasks = [asyncio.create_task(run_plugin(name)) for name in plan.plugins]
        # Run concurrently
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Merge results
        all_issues = []
        all_ghosts = []
        all_flags = []
        for res in results:
            all_issues.extend(res.get("issues", []))
            all_ghosts.extend(res.get("architectural_ghosts", []))
            all_flags.extend(res.get("red_flags", []))

        # Deduplicate issues
        original_issue_count = len(all_issues)
        deduped_issues = self._deduplicate_issues(all_issues)
        deduped_count = len(deduped_issues)
        duplicates_removed = original_issue_count - deduped_count
        if duplicates_removed > 0:
            logger.info(
                "Deduplication: removed %d duplicate issues (%d → %d)",
                duplicates_removed,
                original_issue_count,
                deduped_count,
            )
            all_flags.append(
                "Orchestrator deduplication: removed "
                f"{duplicates_removed} duplicate issues"
            )

        return {
            "issues": deduped_issues,
            "architectural_ghosts": all_ghosts,
            "red_flags": all_flags,
            "plan": plan.to_dict(),
            "metadata": {
                "plugins_run": plan.plugins,
                "total_issues": deduped_count,
                "total_ghosts": len(all_ghosts),
                "deduplication": {
                    "original_count": original_issue_count,
                    "deduped_count": deduped_count,
                    "duplicates_removed": duplicates_removed,
                },
            },
        }

    def _deduplicate_issues(self, issues: list[Any]) -> list[Any]:
        """
        Remove duplicate issues based on file, line, and message fingerprint.
        Preserves order of first occurrence.
        """
        seen = set()
        deduped = []

        for issue in issues:
            key = self._issue_signature(issue)
            if key is None:
                # Cannot deduplicate, keep anyway
                deduped.append(issue)
                continue
            if key not in seen:
                seen.add(key)
                deduped.append(issue)
            # else: skip duplicate

        return deduped

    def _issue_signature(self, issue: Any) -> Optional[str]:
        """
        Create a deduplication signature for an issue.

        Supports:
        - String issues: use whole string (simple)
        - Dict issues: file + line + message fingerprint
        """
        if isinstance(issue, str):
            # Simple: use the normalized string itself
            return issue.lower().strip()

        if isinstance(issue, dict):
            file_path = issue.get('file_path', issue.get('file', None))
            # Line can be single or range; we'll use start only
            line = issue.get('line_start', issue.get('line', None))
            # Message may be under 'message' or 'title' or other
            message = issue.get('message', issue.get('title', issue.get('text', '')))

            if file_path is None or message is None:
                return None  # can't deduplicate reliably

            # Normalize
            file_norm = str(file_path).lower().strip()
            line_norm = str(line).strip()
            msg_norm = str(message)[:100].lower().strip()

            return f"{file_norm}:{line_norm}|{msg_norm}"

        # Unknown type
        return None
