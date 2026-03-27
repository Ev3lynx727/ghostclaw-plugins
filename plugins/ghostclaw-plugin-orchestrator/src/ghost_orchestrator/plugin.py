"""Ghostclaw plugin wrapper for the Orchestrator (experimental)."""

import json
import logging
import os
import sys
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from ghostclaw.core.adapters.base import AdapterMetadata, MetricAdapter
from ghostclaw.core.adapters.hooks import hookimpl
from ghostclaw.core.config import GhostclawConfig
from ghostclaw.core.qmd_store import QMDMemoryStore

from .models import (
    AnalysisPlan,
    OrchestratorConfig,
    PluginCapability,
    RepositoryProfile,
)
from .orchestrator import Orchestrator

logger = logging.getLogger(__name__)


class OrchestratorPlugin(MetricAdapter):
    """
    Ghostclaw plugin that runs the smart orchestrator.

    This plugin selects and runs other analysis plugins adaptively.

    **How it works:**
    1. Discovers available plugins via entry points
    2. Generates a plan using VectorAdvisor (QMD) or LLMPlanner
    3. Executes selected plugins and merges results

    **Configuration:**
    Enable/disable in Ghostclaw config under `orchestrator` key:
    - `use_llm`: bool (default false)
    - `max_plugins`: int (default 8)
    - `vector_weight`, `heuristics_weight`: float (default 0.7, 0.3)

    **Status:** Experimental — real plugin execution implemented (2026-03-19).
    """

    def __init__(self, config: Optional[dict[str, Any]] = None):
        # Store config for backward compatibility; will be overridden by ghost_initialize
        self.config = config or {}
        self.ghostclaw_config = None  # Set by ghost_initialize
        self.registry = None  # Set by ghost_initialize
        self.orchestrator = None

    def get_metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            name="orchestrator",
            version="0.1.1a1",
            description=(
                "Smart plugin orchestration with AI/vector-based "
                "routing (experimental)"
            ),
            dependencies=[],
        )

    async def is_available(self) -> bool:
        return True

    async def ghost_initialize(self, context: Dict[str, Any]) -> None:
        """Dependency injection hook: receives config and registry."""
        from ghostclaw.core.config import GhostclawConfig
        self.ghostclaw_config: GhostclawConfig = context["config"]
        self.registry = context["registry"]
        logger.debug("Orchestrator initialized with Ghostclaw config and registry")

    async def analyze(self, root: str, files: list[str]) -> dict[str, Any]:
        """
        Called by Ghostclaw to perform analysis.

        Args:
            root: Repository root
            files: List of files (ignored by orchestrator)

        Returns:
            Dict with 'issues', 'architectural_ghosts', 'red_flags', 'metadata'
        """
        logger.info(f"Orchestrator analysis requested for {root}")

        # Use injected Ghostclaw config
        orch_config_dict = self.ghostclaw_config.orchestrator.model_dump()
        orch_config = OrchestratorConfig(**orch_config_dict)

        # Determine QMD usage from config
        use_qmd = self.ghostclaw_config.use_qmd

        # Extract real repository profile
        profile = self._extract_repository_profile(root)

        # Discover available plugins via registry (exclude ourselves)
        available_plugins = self._discover_plugins_from_registry()
        if not available_plugins:
            logger.warning(
                "No other plugins discovered; orchestrator will have nothing to run"
            )
            return {
                "issues": [],
                "architectural_ghosts": [],
                "red_flags": ["Orchestrator: no plugins available"],
                "metadata": {"note": "Orchestrator discovered no other plugins"}
            }

        # Build capability descriptors
        capabilities = self._build_plugin_capabilities(available_plugins)

        # Initialize QMD store if enabled
        qmd_store = self._ensure_qmd_store(use_qmd, root)

        # Create orchestrator
        orch = Orchestrator(
            config=orch_config,
            plugin_capabilities=capabilities,
            available_plugins=available_plugins,
            qmd_store=qmd_store,
            repo_profile=profile
        )

        # Plan caching (if enabled)
        cache_key = None
        if orch_config.enable_plan_cache:
            cache_key = self._compute_cache_key(root, profile)

        # Get or generate plan
        plan, used_cache, planning_ms = await self._get_or_create_plan(
            orch,
            orch_config,
            root,
            profile,
            cache_key,
        )

        # Determine if QMD contributed (vector_advisor used actual QMD data)
        qmd_hit = (
            orch.vector_advisor is not None and
            getattr(orch.vector_advisor, 'used_qmd', False)
        )

        # Execute plan (unless plan-only mode)
        if orch_config.plan_only:
            execution_ms = 0.0
            results = {
                "issues": [],
                "architectural_ghosts": [],
                "red_flags": [f"Orchestrator plan-only mode: plan generated but plugins not executed"],
                "metadata": {
                    "plugins_run": [],
                    "plan_only": True,
                }
            }
        else:
            execution_ms, results = await self._execute_plugins(orch, plan, root, files)

        # Assemble final response
        return self._assemble_response(
            results, plan, orch_config, profile, qmd_store,
            used_cache, planning_ms, execution_ms, qmd_hit
        )

    # ------------------------------------------------------------------
    # Refactored helpers
    # ------------------------------------------------------------------
    def _load_global_config(self, root: str) -> tuple:
        """Load Ghostclaw global config and return (config, use_qmd)."""
        try:
            global_cfg = GhostclawConfig.load(root)
            use_qmd = getattr(global_cfg, 'use_qmd', False)
            return global_cfg, use_qmd
        except Exception as e:
            logger.warning(
                "Failed to load Ghostclaw config: %s, defaulting use_qmd=false",
                e,
            )
            return None, False

    def _ensure_qmd_store(self, use_qmd: bool, root: str) -> Optional[QMDMemoryStore]:
        """Create QMDMemoryStore if QMD is enabled; return None otherwise."""
        if not use_qmd:
            return None
        try:
            return self._create_qmd_store(root, self.ghostclaw_config)
        except Exception as e:
            logger.error(
                "Failed to initialize QMD store: %s, falling back to heuristics",
                e,
            )
            return None

    async def _get_or_create_plan(
        self,
        orch: Orchestrator,
        orch_config: OrchestratorConfig,
        root: str,
        profile: RepositoryProfile,
        cache_key: Optional[str],
    ) -> tuple[AnalysisPlan, bool, Optional[float]]:
        """
        Obtain an analysis plan either from cache or by generating a new one.

        Returns:
            (plan, used_cache, planning_ms)
        """
        plan: Optional[AnalysisPlan] = None
        used_cache = False
        planning_ms: Optional[float] = None

        # Try to load from cache if key provided
        if cache_key is not None and orch_config.enable_plan_cache:
            cache_path = self._get_cache_path(orch_config, root)
            cache = self._load_cache(cache_path)
            entry = cache.get(cache_key)
            if entry:
                logger.debug(f"Cache entry found: timestamp={entry.get('timestamp')}")
            if entry and not self._is_expired(entry, orch_config.plan_cache_ttl_hours):
                try:
                    plan = AnalysisPlan.from_dict(entry['plan'])
                    logger.info(f"✅ Using cached analysis plan (key={cache_key})")
                    used_cache = True
                    planning_ms = 0.0
                except Exception as e:
                    logger.warning(f"Failed to restore cached plan: {e}")
                    plan = None
            else:
                if entry:
                    logger.info("Cache entry expired or invalid, will regenerate plan")
                else:
                    logger.info("No cache entry found, will generate plan")

        # Generate plan if not cached
        if plan is None:
            planning_start = time.monotonic()
            plan = await orch.plan(force_llm=orch_config.use_llm)
            planning_ms = (time.monotonic() - planning_start) * 1000
            logger.info(
                "Orchestrator plan: %d plugins, confidence=%.2f",
                len(plan.plugins),
                plan.confidence,
            )
            for i, plugin_name in enumerate(plan.plugins):
                logger.info(f"  {i+1}. {plugin_name}")
            # Store in cache if enabled
            if orch_config.enable_plan_cache and cache_key is not None:
                cache_path = self._get_cache_path(orch_config, root)
                cache = self._load_cache(cache_path)  # reload to avoid race
                cache[cache_key] = {
                    'plan': plan.to_dict(),
                    'timestamp': datetime.utcnow().isoformat(),
                    'repo_profile': {
                        'total_lines': profile.total_lines,
                        'languages': profile.languages,
                        'frameworks': profile.frameworks,
                        'git_branch': profile.git_branch,
                        'git_dirty': profile.git_dirty,
                    }
                }
                self._save_cache(cache_path, cache)
                logger.info(f"Saved analysis plan to cache (key={cache_key})")

        # Verbose output: print plan details to stderr if requested
        if orch_config.verbose:
            print("\n=== Orchestrator Plan ===", file=sys.stderr)
            source = plan.metadata.get('source', 'unknown')
            print(f"Source: {source}", file=sys.stderr)
            print(f"Confidence: {plan.confidence:.2f}", file=sys.stderr)
            print(f"Plugins selected ({len(plan.plugins)}):", file=sys.stderr)
            for i, name in enumerate(plan.plugins, 1):
                print(f"  {i}. {name}", file=sys.stderr)
                # Print rationale if available
                idx = i - 1
                if idx < len(plan.rationale):
                    rationale = plan.rationale[idx]
                    if rationale:
                        # Wrap rationale to 80 chars
                        import textwrap
                        wrapped = textwrap.wrap(rationale, width=76, initial_indent="     → ", subsequent_indent="       ")
                        for line in wrapped:
                            print(line, file=sys.stderr)
            if used_cache:
                print("(Plan loaded from cache)", file=sys.stderr)
            print("========================\n", file=sys.stderr)

        return plan, used_cache, planning_ms

    async def _execute_plugins(
        self, orch: Orchestrator, plan: AnalysisPlan, root: str, files: list[str]
    ) -> tuple[float, dict[str, Any]]:
        """
        Execute the plan using the orchestrator's parallel execution engine.

        Returns:
            (execution_ms, results_dict)
        """
        execution_start = time.monotonic()
        results = await orch.execute_plan(
            plan,
            plugin_executor=lambda name: self._execute_plugin(name, root, files)
        )
        execution_ms = (time.monotonic() - execution_start) * 1000
        return execution_ms, results

    def _assemble_response(
        self,
        results: dict[str, Any],
        plan: AnalysisPlan,
        orch_config: OrchestratorConfig,
        profile: RepositoryProfile,
        qmd_store: Optional[QMDMemoryStore],
        used_cache: bool,
        planning_ms: Optional[float],
        execution_ms: float,
        qmd_hit: bool = False
    ) -> dict[str, Any]:
        """
        Build the final response with metrics, metadata, and red flags.
        """
        total_ms = (planning_ms or 0.0) + execution_ms

        # Build metrics
        metrics: dict[str, Any] = {
            "planning_duration_ms": planning_ms,
            "execution_duration_ms": execution_ms,
            "total_duration_ms": total_ms,
            "plugins_planned": len(plan.plugins),
            "plugins_executed": len(results.get("metadata", {}).get("plugins_run", [])),
            "concurrency_used": orch_config.max_concurrent_plugins,
            "cache_hit": used_cache,
            "qmd_hit": qmd_hit,
        }

        # LLM token usage if present
        if "llm_usage" in plan.metadata:
            metrics["llm_token_usage"] = plan.metadata["llm_usage"]

        # Add orchestrator's own red flags summarizing the plan
        red_flags = results.get("red_flags", [])
        red_flags.insert(0, f"Orchestrator selected: {', '.join(plan.plugins)}")
        if plan.metadata.get('source'):
            red_flags.insert(1, f"Plan source: {plan.metadata['source']}")
        results["red_flags"] = red_flags

        # Ensure orchestrator plan and execution metadata are present
        md = results.setdefault("metadata", {})
        md["orchestrator_plan"] = plan.to_dict()
        md["note"] = "Orchestrator executed selected plugins"
        md["qmd_enabled"] = qmd_store is not None
        md["repo_profile"] = {
            "total_lines": profile.total_lines,
            "languages": profile.languages,
            "frameworks": profile.frameworks,
        }
        md["orchestrator_metrics"] = metrics

        # Add total_ms to metrics
        metrics["total_duration_ms"] = total_ms

        return results

    def _extract_repository_profile(self, root: str) -> RepositoryProfile:
        """Extract repository features: languages, lines, frameworks, git info."""
        root_path = Path(root)
        profile = RepositoryProfile(path=str(root_path))

        # Count languages and total lines
        lang_counts, total_lines = self._count_languages(root_path)
        profile.languages = lang_counts
        profile.total_lines = total_lines

        # Detect frameworks from dependency files
        profile.frameworks = self._detect_frameworks(root_path)

        # Git information (best effort)
        has_git, branch, dirty = self._detect_git_info(root)
        profile.has_git = has_git
        profile.git_branch = branch
        profile.git_dirty = dirty

        # File patterns (stub/placeholder)
        profile.file_patterns = {}

        return profile

    def _count_languages(self, root_path: Path) -> tuple[dict[str, int], int]:
        """Count lines of code per language by walking the repository."""
        lang_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.hh': 'cpp',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.m': 'objective-c',
            '.mm': 'objective-c++',
            '.cs': 'csharp',
            '.fs': 'fsharp',
            '.clj': 'clojure',
            '.ex': 'elixir',
            '.exs': 'elixir',
            '.erl': 'erlang',
            '.hrl': 'erlang',
            '.hs': 'haskell',
            '.ml': 'ocaml',
            '.mli': 'ocaml',
            '.r': 'r',
            '.R': 'r',
            '.sh': 'bash',
            '.bash': 'bash',
            '.zsh': 'bash',
            '.fish': 'fish',
            '.ps1': 'powershell',
            '.psm1': 'powershell',
            '.psd1': 'powershell',
            '.sql': 'sql',
            '.html': 'html',
            '.htm': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sass': 'sass',
            '.less': 'less',
            '.xml': 'xml',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.toml': 'toml',
            '.ini': 'ini',
            '.cfg': 'ini',
            '.conf': 'conf',
            '.md': 'markdown',
            '.rst': 'rst',
            '.tex': 'latex',
            '.vb': 'vb',
            '.vbs': 'vb',
            '.dart': 'dart',
            '.lua': 'lua',
            '.pl': 'perl',
            '.pm': 'perl',
            '.tcl': 'tcl',
            '.tk': 'tcl',
            '.v': 'verilog',
            '.sv': 'systemverilog',
            '.vhd': 'vhdl',
            '.vhdl': 'vhdl',
            '.tf': 'terraform',
            '.hcl': 'hcl',
        }

        total_lines = 0
        lang_counts: dict[str, int] = {}

        exclude_dirs = {
            '.git', '.ghostclaw', '__pycache__', 'node_modules', 'venv', '.venv',
            'env', '.env', 'target', 'build', 'dist', '.tox', 'coverage', '.coverage',
            'htmlcov', '.pytest_cache', '.mypy_cache', '.ruff_cache', '.idea',
            '.vscode', '.vs', 'tmp', 'temp', 'logs', 'log'
        }

        for file_path in root_path.rglob('*'):
            lines = self._safe_count_lines(file_path, lang_map, exclude_dirs)
            if lines <= 0:
                continue
            lang = lang_map.get(file_path.suffix.lower())
            if not lang:
                continue
            lang_counts[lang] = lang_counts.get(lang, 0) + lines
            total_lines += lines

        return lang_counts, total_lines

    def _safe_count_lines(
        self,
        file_path: Path,
        lang_map: dict[str, str],
        exclude_dirs: set[str],
    ) -> int:
        """Return number of lines if file qualifies, else 0. Ignores errors."""
        if file_path.is_dir():
            return 0
        if any(part in exclude_dirs for part in file_path.parts):
            return 0
        ext = file_path.suffix.lower()
        lang = lang_map.get(ext)
        if not lang:
            return 0
        try:
            return self._count_file_lines(file_path)
        except Exception:
            return 0

    def _count_file_lines(self, file_path: Path) -> int:
        """Count lines in a file, skipping if too large."""
        if file_path.stat().st_size > 10 * 1024 * 1024:
            return 0
        with open(file_path, encoding='utf-8', errors='ignore') as f:
            return sum(1 for _ in f)

    def _detect_frameworks(self, root_path: Path) -> list[str]:
        """Detect frameworks from dependency files."""
        dep_files = {
            'requirements.txt': 'python',
            'Pipfile': 'python',
            'pyproject.toml': 'python',
            'setup.py': 'python',
            'package.json': 'javascript',
            'yarn.lock': 'javascript',
            'pnpm-lock.yaml': 'javascript',
            'bower.json': 'javascript',
            'Cargo.toml': 'rust',
            'go.mod': 'go',
            'Gemfile': 'ruby',
            'composer.json': 'php',
            'pom.xml': 'java',
            'build.gradle': 'java',
            'build.gradle.kts': 'java',
            'settings.gradle': 'java',
            'CMakeLists.txt': 'cpp',
            'Makefile': 'make',
            'Dockerfile': 'docker',
            'docker-compose.yml': 'docker',
            'docker-compose.yaml': 'docker',
            'Rakefile': 'ruby',
            'mix.exs': 'elixir',
            'rebar.config': 'erlang',
            'Cargo.lock': 'rust',
            'vendor/dependencies': 'go',
            'go.sum': 'go',
            'Podfile': 'swift',
            'Cartfile': 'swift',
        }

        frameworks = []
        for file_name, fw in dep_files.items():
            if (root_path / file_name).exists():
                frameworks.append(fw)
        return list(set(frameworks))

    def _detect_git_info(self, root: str) -> tuple[bool, Optional[str], bool]:
        """Detect git repository information."""
        try:
            # Check if inside a git repo
            result = subprocess.run(
                ['git', 'rev-parse', '--is-inside-work-tree'],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=2
            )
            has_git = result.returncode == 0 and result.stdout.strip() == 'true'
            if not has_git:
                return False, None, False

            # Current branch
            branch_result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if branch_result.returncode == 0:
                branch = branch_result.stdout.strip()
            else:
                branch = None

            # Dirty status
            dirty_result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=2
            )
            dirty = bool(dirty_result.stdout.strip())

            return True, branch, dirty
        except Exception:
            return False, None, False

    def _create_qmd_store(self, root: str, global_cfg) -> Optional[QMDMemoryStore]:
        """Instantiate QMDMemoryStore using Ghostclaw's configuration."""
        db_path = Path(root) / ".ghostclaw" / "storage" / "qmd" / "ghostclaw.db"

        # Extract configuration from GhostclawConfig
        embedding_backend = getattr(global_cfg, 'embedding_backend', 'fastembed')
        ai_buff_enabled = getattr(global_cfg, 'ai_buff_enabled', False)
        prefetch_enabled = getattr(global_cfg, 'prefetch_enabled', True)
        prefetch_workers = getattr(global_cfg, 'prefetch_workers', 2)
        prefetch_window = getattr(global_cfg, 'prefetch_window', 2)
        prefetch_hours = getattr(global_cfg, 'prefetch_hours', 24)
        prefetch_vibe_delta = getattr(global_cfg, 'prefetch_vibe_delta', 10)
        prefetch_stack_count = getattr(global_cfg, 'prefetch_stack_count', 5)
        auto_migrate = getattr(global_cfg, 'auto_migrate', True)
        migration_batch_size = getattr(global_cfg, 'migration_batch_size', 50)
        migration_throttle_ms = getattr(global_cfg, 'migration_throttle_ms', 100)
        max_chunks_per_report = getattr(global_cfg, 'max_chunks_per_report', None)
        vector_index_config = {}
        if hasattr(global_cfg, 'vector_index'):
            vector_index_config = getattr(global_cfg, 'vector_index', {})

        store = QMDMemoryStore(
            db_path=db_path,
            use_enhanced=True,
            embedding_backend=embedding_backend,
            ai_buff_enabled=ai_buff_enabled,
            prefetch_enabled=prefetch_enabled,
            prefetch_workers=prefetch_workers,
            prefetch_window=prefetch_window,
            prefetch_hours=prefetch_hours,
            prefetch_vibe_delta=prefetch_vibe_delta,
            prefetch_stack_count=prefetch_stack_count,
            auto_migrate=auto_migrate,
            migration_batch_size=migration_batch_size,
            migration_throttle_ms=migration_throttle_ms,
            max_chunks_per_report=max_chunks_per_report,
            vector_index_config=vector_index_config,
        )

        # Ensure directory exists
        store.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize vector index if requested
        if store.vector_index_config.get('enabled', False):
            self._initialize_vector_index(store)

        return store

    def _initialize_vector_index(self, store: QMDMemoryStore) -> None:
        """Initialize vector index based on configuration."""
        index_type = store.vector_index_config.get('type', 'ivf_pq')
        vector_cfg = store.vector_index_config.get('ivf_pq', {})

        if index_type != 'ivf_pq':
            return

        self._create_ivf_pq_index(store, vector_cfg)

    def _create_ivf_pq_index(self, store: QMDMemoryStore, vector_cfg: dict) -> None:
        """Create IVF-PQ index with given configuration."""
        index_config = {
            'num_partitions': vector_cfg.get('partitions', 128),
            'sub_vectors': vector_cfg.get('sub_vectors', 16),
            'training_sample_size': vector_cfg.get('training_sample_size', 100000),
        }

        try:
            store.vector_store.ensure_index(
                column='embedding',
                index_type='ivf_pq',
                index_config=index_config
            )
        except Exception as e:
            logger.error("Failed to create IVF-PQ index: %s", e)

    def _build_plugin_capabilities(
        self,
        plugin_names: list[str],
    ) -> dict[str, PluginCapability]:
        """Return PluginCapability objects for known plugins; use generic stubs
        for others."""
        known_capabilities = {
            'bandit': PluginCapability(
                name='bandit',
                description=(
                    "Security scanner for Python code (Bandit)"
                ),
                categories=['security'],
                languages=['python'],
                min_codebase_size=0,
                max_codebase_size=10_000_000
            ),
            'coderabbit': PluginCapability(
                name='coderabbit',
                description='AI-powered code review using CodeRabbit',
                categories=['review', 'ai'],
                languages=[],  # supports many
                min_codebase_size=0,
                max_codebase_size=500_000
            ),
            'lizard': PluginCapability(
                name='lizard',
                description='Code complexity analyzer (Cyclomatic, Cognitive)',
                categories=['complexity', 'metrics'],
                languages=[],  # polyglot
                min_codebase_size=0,
                max_codebase_size=10_000_000
            ),
            'pyscn': PluginCapability(
                name='pyscn',
                description='Structural clone and dead code detection for Python',
                categories=['duplication', 'dead-code'],
                languages=['python'],
                min_codebase_size=0,
                max_codebase_size=10_000_000
            ),
            'ai-codeindex': PluginCapability(
                name='ai-codeindex',
                description='Deep architectural analysis and symbol indexing',
                categories=['architecture', 'indexing'],
                languages=[],  # polyglot
                min_codebase_size=1000,
                max_codebase_size=10_000_000
            ),
        }

        capabilities = {}
        for name in plugin_names:
            if name in known_capabilities:
                capabilities[name] = known_capabilities[name]
            else:
                # Generic stub
                capabilities[name] = PluginCapability(
                    name=name,
                    description=f'{name} plugin (capabilities unknown)',
                    categories=[],
                    languages=[],
                    min_codebase_size=0,
                    max_codebase_size=10_000_000
                )
        return capabilities

    # ------------------------------------------------------------------
    # Plan Caching
    # ------------------------------------------------------------------
    def _get_cache_path(self, orch_config: OrchestratorConfig, root: str) -> Path:
        """Determine cache file path.
        If cache_dir is set, use that directory (absolute or relative to root).
        Otherwise, default to .ghostclaw/storage/ inside repo.
        """
        if orch_config.cache_dir:
            p = Path(orch_config.cache_dir)
            if not p.is_absolute():
                # Interpret relative to repository root
                p = Path(root) / p
            return p / "orchestrator_plan_cache.json"
        if orch_config.plan_cache_file:
            p = Path(orch_config.plan_cache_file)
            if p.is_absolute():
                return p
            return Path(root) / p
        # Default: inside repo's .ghostclaw/storage/
        return Path(root) / ".ghostclaw" / "storage" / "orchestrator_plan_cache.json"

    def _compute_cache_key(self, root: str, profile: RepositoryProfile) -> str:
        """
        Compute a cache key that changes when the repo changes.
        Use git commit if available; otherwise use mtime of root.
        """
        if profile.has_git and profile.git_branch:
            # Use branch name + last commit? Better: use HEAD commit SHA if we can
            # get it.
            try:
                result = subprocess.run(
                    ['git', 'rev-parse', 'HEAD'],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0:
                    commit_sha = result.stdout.strip()[:12]  # short SHA
                    return f"git:{commit_sha}"
            except Exception:
                pass
        # Fallback: use mtime of the root directory
        try:
            mtime = os.path.getmtime(root)
            return f"mtime:{mtime}"
        except Exception:
            return f"path:{root}"

    def _load_cache(self, cache_path: Path) -> dict[str, Any]:
        """Load the cache file if it exists."""
        if not cache_path.exists():
            return {}
        try:
            with open(cache_path) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load orchestrator cache: {e}")
            return {}

    def _save_cache(self, cache_path: Path, cache: dict[str, Any]) -> None:
        """Save cache to disk."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(cache_path, 'w') as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save orchestrator cache: {e}")

    def _is_expired(self, entry: dict[str, Any], ttl_hours: int) -> bool:
        """Check if a cache entry is expired based on timestamp."""
        if ttl_hours <= 0:
            return False  # no expiration
        ts_str = entry.get('timestamp')
        if not ts_str:
            return True
        try:
            ts = datetime.fromisoformat(ts_str)
            cutoff = datetime.utcnow() - timedelta(hours=ttl_hours)
            return ts < cutoff
        except Exception:
            return True

    async def _execute_plugin(
        self,
        plugin_name: str,
        root: str,
        files: list[str],
    ) -> dict[str, Any]:
        """Instantiate and run a single plugin."""
        from importlib.metadata import entry_points
        # Find the entry point
        eps = entry_points(group='ghostclaw.plugins')
        ep = next((e for e in eps if e.name == plugin_name), None)
        if not ep:
            raise ValueError(f"Plugin {plugin_name} not found in entry points")

        # Load and instantiate the plugin class
        plugin_cls = ep.load()
        # Most plugins don't take constructor args (or take optional config)
        try:
            plugin_instance = plugin_cls()
        except TypeError:
            # Fallback: try with empty config
            plugin_instance = plugin_cls(config={})

        # Call analyze — could be async or sync
        if hasattr(plugin_instance, 'analyze'):
            # Check if it's async
            import inspect
            if inspect.iscoroutinefunction(plugin_instance.analyze):
                result = await plugin_instance.analyze(root, files)
            else:
                result = plugin_instance.analyze(root, files)
            return result
        else:
            raise NotImplementedError(f"Plugin {plugin_name} has no analyze() method")

    def _discover_plugins(self) -> list[str]:
        """Discover other Ghostclaw plugins via entry points (legacy fallback)."""
        try:
            from importlib.metadata import entry_points
            eps = entry_points(group='ghostclaw.plugins')
            return [e.name for e in eps if e.name != 'orchestrator']
        except Exception as e:
            logger.error(f"Plugin discovery failed: {e}")
            return []

    def _discover_plugins_from_registry(self) -> list[str]:
        """Discover other Ghostclaw plugins from the injected registry."""
        names = []
        for name, plugin in self.registry.pm.list_name_plugin():
            if name == "orchestrator":
                continue
            if hasattr(plugin, "ghost_analyze"):
                names.append(name)
        return names

    @hookimpl
    async def ghost_analyze(self, root: str, files: list[str]) -> dict[str, Any]:
        """Hook implementation."""
        return await self.analyze(root, files)

    @hookimpl
    def ghost_get_metadata(self) -> dict[str, Any]:
        """Metadata hook."""
        meta = self.get_metadata()
        return {
            "name": meta.name,
            "version": meta.version,
            "description": meta.description,
            "available": True
        }
