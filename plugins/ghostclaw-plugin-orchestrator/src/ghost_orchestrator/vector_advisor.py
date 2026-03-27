"""Vector-based plugin advisor using QMD embeddings."""

import logging

from .models import (
    OrchestratorConfig,
    PluginCapability,
    RepositoryProfile,
)

logger = logging.getLogger(__name__)


class VectorAdvisor:
    """Recommends plugins based on similarity to past analysis runs."""

    def __init__(
        self,
        qmd_store,
        plugin_capabilities: dict[str, PluginCapability],
        config: OrchestratorConfig,
    ):
        """
        Args:
            qmd_store: QMDMemoryStore instance for vector queries
            plugin_capabilities: Mapping of plugin name → capability metadata
            config: Orchestrator configuration
        """
        self.qmd_store = qmd_store
        self.plugin_capabilities = plugin_capabilities
        self.config = config
        self.used_qmd = False  # Whether QMD provided data for scoring

    async def recommend(
        self,
        repo_profile: RepositoryProfile,
        available_plugins: list[str],
    ) -> list[tuple[str, float, str]]:
        """
        Recommend plugins based on vector similarity.

        Returns:
            List of (plugin_name, score, reason) sorted by score descending
        """
        if self.qmd_store is None:
            logger.info("QMD store not available, using heuristics")
            return self._heuristic_fallback(repo_profile, available_plugins)

        try:
            # Query QMD for similar past runs
            similar_runs = await self._find_similar_runs(repo_profile)

            if not similar_runs:
                logger.info("No similar runs found, falling back to heuristics")
                return self._heuristic_fallback(repo_profile, available_plugins)

            # Score plugins based on historical effectiveness
            plugin_scores = self._score_plugins_from_runs(
                similar_runs, available_plugins
            )

            # Normalize scores to 0-1
            if plugin_scores:
                max_score = max(score for _, score in plugin_scores)
                plugin_scores = [
                    (p, s / max_score, self._explain_score(p, s, similar_runs))
                    for p, s in plugin_scores
                ]

            return sorted(plugin_scores, key=lambda x: x[1], reverse=True)

        except Exception as e:
            logger.error(f"Vector advisor failed: {e}, falling back to heuristics")
            return self._heuristic_fallback(repo_profile, available_plugins)

    async def _find_similar_runs(
        self,
        repo_profile: RepositoryProfile,
        limit: int = 20,
    ) -> list[dict]:
        """Find past analysis runs with similar codebases."""
        # Build a simple token-based query for FTS + vector search
        tokens = ["code", "repository"]

        # Add language tokens (e.g., python, javascript)
        if repo_profile.languages:
            tokens.extend(list(repo_profile.languages.keys()))

        # Add framework tokens
        if repo_profile.frameworks:
            tokens.extend(repo_profile.frameworks)

        # Add size token
        if repo_profile.total_lines < 1000:
            tokens.append("small")
        elif repo_profile.total_lines < 10000:
            tokens.append("medium")
        else:
            tokens.append("large")

        query = " ".join(tokens)

        try:
            results = await self.qmd_store.search(
                query=query,
                limit=limit,
                alpha=0.8,  # vector-biased for similarity
            )
            if results:
                self.used_qmd = True
            return results
        except Exception as e:
            logger.error(f"QMD search failed: {e}")
            return []

    def _score_plugins_from_runs(
        self,
        runs: list[dict],
        available_plugins: list[str],
    ) -> list[tuple[str, float]]:
        """
        Score plugins based on how often they produced valuable issues
        in similar runs.
        """
        plugin_stats = self._accumulate_run_stats(runs, available_plugins)
        return self._compute_plugin_scores(plugin_stats)

    def _accumulate_run_stats(
        self,
        runs: list[dict],
        available_plugins: list[str],
    ) -> dict[str, dict[str, float]]:
        """Iterate runs and accumulate counts per plugin."""
        plugin_stats: dict[str, dict[str, float]] = {}

        for run in runs:
            run_metadata = run.get("metadata", {})
            plugins_used = run_metadata.get("plugins_used", [])

            # Count issues per plugin in this run
            issues_by_plugin: dict[str, int] = {}
            for issue in run.get("issues", []):
                plugin = issue.get("plugin", "unknown")
                issues_by_plugin[plugin] = issues_by_plugin.get(plugin, 0) + 1

            # Update running stats
            for plugin in plugins_used:
                if plugin not in available_plugins:
                    continue  # skip plugins not currently available

                if plugin not in plugin_stats:
                    plugin_stats[plugin] = {"runs": 0, "issues": 0}

                plugin_stats[plugin]["runs"] += 1
                plugin_stats[plugin]["issues"] += issues_by_plugin.get(plugin, 0)

        return plugin_stats

    def _compute_plugin_scores(
        self,
        plugin_stats: dict[str, dict[str, float]],
    ) -> list[tuple[str, float]]:
        """Convert stats into normalized 0-1 scores."""
        scores = []
        for plugin, stats in plugin_stats.items():
            if stats["runs"] == 0:
                continue
            avg_issues = stats["issues"] / stats["runs"]
            # Normalize to 0-1 (assuming 10 issues is max typical)
            score = min(avg_issues / 10.0, 1.0)
            scores.append((plugin, score))
        return scores

    def _heuristic_fallback(
        self,
        repo_profile: RepositoryProfile,
        available_plugins: list[str],
    ) -> list[tuple[str, float, str]]:
        """Fallback scoring based on simple heuristics."""
        scores = []

        for plugin_name in available_plugins:
            capability = self.plugin_capabilities.get(plugin_name)
            if not capability:
                continue

            score = 0.0
            reasons = []

            # Language match (capability may not have languages)
            plugin_langs = getattr(capability, 'languages', [])
            lang_match = len(set(repo_profile.languages.keys()) & set(plugin_langs))
            if lang_match > 0:
                score += 0.4
                reasons.append(f"matches languages {plugin_langs}")

            # Size suitability
            min_size = getattr(capability, 'min_codebase_size', 0)
            max_size = getattr(capability, 'max_codebase_size', 10_000_000)
            total = repo_profile.total_lines
            if min_size <= total <= max_size:
                score += 0.3
                reasons.append("appropriate for codebase size")

            # Base score for any plugin
            score += 0.1
            reasons.append("general capability")

            reason = "; ".join(reasons) if reasons else "no strong signal"
            scores.append((plugin_name, score, reason))

        return sorted(scores, key=lambda x: x[1], reverse=True)

    def _explain_score(
        self,
        plugin: str,
        score: float,
        runs: list[dict],
    ) -> str:
        """Generate a human-readable explanation for the score."""
        # Find runs where this plugin was used
        relevant_runs = [
            r for r in runs
            if plugin in r.get("metadata", {}).get("plugins_used", [])
        ]

        if not relevant_runs:
            return "No historical data"

        avg_issues = (
            sum(
                len([i for i in r.get("issues", []) if i.get("plugin") == plugin])
                for r in relevant_runs
            )
            / len(relevant_runs)
        )

        return (
            f"Based on {len(relevant_runs)} similar runs, "
            f"averaged {avg_issues:.1f} issues"
        )
