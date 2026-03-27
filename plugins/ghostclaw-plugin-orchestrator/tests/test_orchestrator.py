"""Tests for ghost-orchestrator."""

import pytest

from ghost_orchestrator.models import (
    AnalysisPlan,
    OrchestratorConfig,
    PluginCapability,
    RepositoryProfile,
)
from ghost_orchestrator.orchestrator import Orchestrator
from ghost_orchestrator.vector_advisor import VectorAdvisor


class TestOrchestratorConfig:
    """Test configuration validation."""

    def test_valid_config(self):
        config = OrchestratorConfig(
            use_llm=False,
            vector_weight=0.7,
            heuristics_weight=0.3
        )
        assert config.vector_weight + config.heuristics_weight == 1.0

    def test_invalid_weights_sum(self):
        with pytest.raises(ValueError):
            OrchestratorConfig(vector_weight=0.8, heuristics_weight=0.3)


class TestRepositoryProfile:
    """Test repository profile extraction."""

    def test_profile_creation(self):
        profile = RepositoryProfile(
            path="/tmp/repo",
            languages={"python": 5000, "javascript": 2000},
            total_lines=7000,
            frameworks=["django", "react"]
        )
        summary = profile.summary()
        assert "python" in summary
        assert "django" in summary
        assert "7000" in summary


class TestAnalysisPlan:
    """Test analysis plan structure."""

    def test_plan_serialization(self):
        plan = AnalysisPlan(
            plugins=["bandit", "pylint"],
            rationale=["Security check", "Style guide"],
            confidence=0.8
        )
        d = plan.to_dict()
        assert d["plugins"] == ["bandit", "pylint"]
        assert d["confidence"] == 0.8


class TestVectorAdvisor:
    """Test vector-based plugin recommendation."""

    @pytest.fixture
    def capabilities(self):
        return {
            "bandit": PluginCapability(
                name="bandit",
                description="Security scanner",
                categories=["security"],
                languages=["python"]
            ),
            "pylint": PluginCapability(
                name="pylint",
                description="Style linter",
                categories=["style"],
                languages=["python"]
            )
        }

    @pytest.mark.asyncio
    async def test_heuristic_fallback_when_no_qmd(self, capabilities):
        advisor = VectorAdvisor(
            qmd_store=None,
            plugin_capabilities=capabilities,
            config=OrchestratorConfig()
        )
        profile = RepositoryProfile(
            path="/tmp/repo",
            languages={"python": 1000},
            total_lines=1000
        )
        recs = await advisor.recommend(profile, ["bandit", "pylint"])
        assert len(recs) > 0
        # Should have scores and reasons
        for plugin, score, reason in recs:
            assert 0 <= score <= 1
            assert reason


class TestOrchestrator:
    """Test main orchestrator logic."""

    @pytest.fixture
    def capabilities(self):
        return {
            "bandit": PluginCapability(
                name="bandit",
                description="Security scanner",
                categories=["security"],
                languages=["python"]
            )
        }

    def test_orchestrator_creation(self, capabilities):
        config = OrchestratorConfig(use_llm=False)
        orch = Orchestrator(
            config=config,
            plugin_capabilities=capabilities,
            available_plugins=["bandit"],
            repo_path="/tmp/fake_repo"
        )
        assert orch.repo_profile.path == "/tmp/fake_repo"

    @pytest.mark.asyncio
    async def test_plan_generation(self, capabilities):
        config = OrchestratorConfig(use_llm=False)
        orch = Orchestrator(
            config=config,
            plugin_capabilities=capabilities,
            available_plugins=["bandit"],
            repo_path="/tmp/fake_repo"
        )
        plan = await orch.plan()
        assert isinstance(plan, AnalysisPlan)
        assert len(plan.plugins) > 0

    def test_deduplication_strings(self, capabilities):
        config = OrchestratorConfig()
        orch = Orchestrator(
            config=config,
            plugin_capabilities=capabilities,
            available_plugins=[],
            repo_path="/tmp/fake_repo"
        )
        issues = [
            "file.py:10 - Something wrong",
            "file.py:10 - Something wrong",  # exact duplicate
            "file.py:10 - Something Wrong",  # case variation
            "other.py:20 - Another issue",
        ]
        deduped = orch._deduplicate_issues(issues)
        assert len(deduped) == 2
        assert "file.py:10 - Something wrong" in deduped
        assert "other.py:20 - Another issue" in deduped

    def test_deduplication_dicts(self, capabilities):
        config = OrchestratorConfig()
        orch = Orchestrator(
            config=config,
            plugin_capabilities=capabilities,
            available_plugins=[],
            repo_path="/tmp/fake_repo"
        )
        issues = [
            {'file_path': 'a.js', 'line_start': 5, 'message': 'Error'},
            {'file_path': 'a.js', 'line_start': 5, 'message': 'Error'},  # duplicate
            {'file_path': 'a.js', 'line_start': 6, 'message': 'Error'},  # different line
            {'file_path': 'b.js', 'line_start': 5, 'message': 'Error'},
        ]
        deduped = orch._deduplicate_issues(issues)
        assert len(deduped) == 3
        # Check that duplicate was removed
        seen_signatures = set()
        for issue in deduped:
            sig = orch._issue_signature(issue)
            assert sig not in seen_signatures
            seen_signatures.add(sig)

    def test_deduplication_mixed_types(self, capabilities):
        config = OrchestratorConfig()
        orch = Orchestrator(
            config=config,
            plugin_capabilities=capabilities,
            available_plugins=[],
            repo_path="/tmp/fake_repo"
        )
        issues = [
            "string issue",
            {'file_path': 'file.py', 'line_start': 1, 'message': 'string issue'},
        ]
        deduped = orch._deduplicate_issues(issues)
        # Different signatures, both kept
        assert len(deduped) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
