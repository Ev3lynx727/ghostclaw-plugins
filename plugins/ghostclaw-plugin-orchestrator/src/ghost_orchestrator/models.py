"""Data models for the orchestrator."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class PluginCapability:
    """What a plugin can detect."""
    name: str
    description: str
    categories: list[str]  # e.g., ["security", "performance", "style"]
    languages: list[str] = field(default_factory=list)  # e.g., ["python", "js"]
    min_codebase_size: int = 0  # lines of code
    max_codebase_size: int = 10_000_000


@dataclass
class RepositoryProfile:
    """Extracted features of a repository."""
    path: str
    languages: dict[str, int] = field(default_factory=dict)  # {lang: lines}
    frameworks: list[str] = field(default_factory=list)
    total_lines: int = 0
    has_git: bool = False
    git_branch: Optional[str] = None
    git_dirty: bool = False
    file_patterns: dict[str, int] = field(default_factory=dict)
    # patterns → count
    # Could include more: dependency files present, CI config,
    # test coverage indicators, etc.

    def summary(self) -> str:
        """Human-readable description for LLM prompts."""
        lang_str = ", ".join(f"{k} ({v}LOC)" for k, v in self.languages.items())
        return (
            f"Repository at {self.path}\n"
            f"Languages: {lang_str or 'unknown'}\n"
            f"Frameworks: {', '.join(self.frameworks) or 'none detected'}\n"
            f"Total lines: {self.total_lines}\n"
            f"Git: {'yes' if self.has_git else 'no'}"
        )


@dataclass
class PluginRunRecord:
    """Historical record of a plugin execution."""
    plugin_name: str
    run_id: str
    repository_similarity: float  # 0-1, how similar to current repo
    issues_found: int
    false_positive_estimate: float  # 0-1
    execution_time_ms: int
    timestamp: datetime


@dataclass
class AnalysisPlan:
    """Ordered plan for which plugins to run."""
    plugins: list[str]  # plugin names in execution order
    rationale: list[str]  # one per plugin, explaining choice
    confidence: float  # 0-1, how confident we are this plan is good
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugins": self.plugins,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'AnalysisPlan':
        return cls(
            plugins=data['plugins'],
            rationale=data['rationale'],
            confidence=data['confidence'],
            metadata=data.get('metadata', {})
        )


@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator."""
    # Core routing flags
    use_llm: bool = False
    vector_weight: float = 0.7
    heuristics_weight: float = 0.3
    max_plugins: int = 8
    plugin_history_lookback: int = 50
    llm_model: Optional[str] = None
    max_concurrent_plugins: int = 4

    # Plan caching
    enable_plan_cache: bool = False
    plan_cache_ttl_hours: int = 24
    plan_cache_file: Optional[str] = None

    # v0.2.4 enhancements
    verbose: bool = False
    cache_dir: Optional[str] = None

    # Additional fields from Ghostclaw core config (for compatibility)
    enabled: bool = False
    llm_temperature: float = 0.7
    max_tokens: int = 4096
    plan_only: bool = False
    report_plan_details: bool = True
    concurrency_limit: Optional[int] = None

    def __post_init__(self):
        total = self.vector_weight + self.heuristics_weight
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        if self.max_concurrent_plugins < 1:
            raise ValueError("max_concurrent_plugins must be >= 1")
        if self.plan_cache_ttl_hours < 0:
            raise ValueError("plan_cache_ttl_hours must be >= 0")
