# Ghost Orchestrator

**Experimental adaptive plugin routing for Ghostclaw.**

*"Let the LLM conduct the plugin orchestra — or keep it simple with smart heuristics."*

---

## ⚠️ Prerequisites

- **Ghostclaw ≥ 0.2.1b0** (v0.2+ with QMD support). Install from GitHub:  
  `pip install ghostclaw==0.2.1b0` (released version with QMD)
- **QMD enabled** for full functionality:  
  `ghostclaw config set use_qmd true`

Without QMD history, the orchestrator falls back to heuristic scoring only.

---

## 🎯 What Is It?

Ghost Orchestrator is an experimental **plugin router** for Ghostclaw that intelligently selects which analysis plugins to run on a repository. Instead of running every plugin, it:

1. **Discovers** available plugins via entry points
2. **Examines** the repository (languages, size, file patterns)
3. **Consults** past analysis history via QMD vector similarity (if enabled)
4. **Optionally** asks an LLM to create a plan
5. **Executes** selected plugins in parallel (configurable concurrency)
6. **Deduplicates** issues and aggregates results into a single report

**Goal:** Reduce noise, improve relevance, and lower compute cost by avoiding unnecessary plugin runs.

**Compatibility:** Requires Ghostclaw **v0.2.1-beta** or later (v0.2+). Depends on QMD storage, plugin auto-discovery, and async adapter infrastructure.

---

## 🏗️ Architecture

```
┌─────────────┐
│ Repository  │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│          Ghost Orchestrator                   │
│  ┌────────────────────────────────────────┐  │
│  │ 1. Discover Plugins                    │  │
│  │    - Scan entry points                 │  │
│  │    - Load capabilities                 │  │
│  └────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────┐  │
│  │ 2. Generate Analysis Plan              │  │
│  │    ├─ VectorAdvisor (QMD similarity)  │  │
│  │    ├─ HeuristicFallback               │  │
│  │    └─ LLMPlanner (optional)           │  │
│  └────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────┐  │
│  │ 3. Execute Selected Plugins            │  │
│  │    - Parallel or sequential            │  │
│  │    - Merge results                     │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
       │
       ▼
┌─────────────┐
│   Report    │
└─────────────┘
```

---

## 🚀 Quick Start

### Installation

```bash
# From PyPI (once published)
pip install ghost-orchestrator

# Or from local build
pip install dist/ghost_orchestrator-0.1.0a1-py3-none-any.whl

# Or editable install for development
cd plugins/ghostclaw-plugin-orchestrator
pip install -e .
```

This registers `orchestrator` as a Ghostclaw plugin via entry points. No further setup needed.

### Usage

#### Basic: Enable QMD and Run

```bash
# 1. Enable QMD in Ghostclaw (for vector similarity)
ghostclaw config set use_qmd true

# 2. Run analysis — orchestrator auto-loads and selects plugins
ghostclaw analyze /path/to/repo --no-ai --no-cache

# 3. Check the report: you'll see which plugins were selected
# Look in .ghostclaw/storage/reports/ for "Orchestrator selected: ..."
```

Orchestrator runs automatically on every analysis when it's installed. You can adjust its behavior via Ghostclaw config.

---

## ⚙️ Configuration

Add to your Ghostclaw config (`~/.ghostclaw/ghostclaw.json`):

```json
{
  "orchestrator": {
    "use_llm": false,
    "llm_model": "openrouter/anthropic/claude-3-sonnet",
    "vector_weight": 0.7,
    "heuristics_weight": 0.3,
    "max_plugins": 8,
    "max_concurrent_plugins": 4,
    "plugin_history_lookback": 50,
    "enable_plan_cache": true,
    "plan_cache_ttl_hours": 24
  }
}
```

**Options:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `use_llm` | bool | `false` | Use LLM for planning instead of vector+heuristics |
| `llm_model` | string | `openrouter/anthropic/claude-3-sonnet` | Model to use when `use_llm=true` |
| `vector_weight` | float | `0.7` | Weight given to QMD vector similarity (0-1) |
| `heuristics_weight` | float | `0.3` | Weight given to rule-based heuristics (0-1) |
| `max_plugins` | int | `8` | Maximum plugins to execute per analysis |
| `max_concurrent_plugins` | int | `4` | How many plugins to run concurrently (async) |
| `plugin_history_lookback` | int | `50` | How many past runs to consider for vector scoring |
| `enable_plan_cache` | bool | `true` | Cache analysis plans to avoid re-planning |
| `plan_cache_ttl_hours` | int | `24` | How long to keep a cached plan (TTL) |

**Note:** Plugin capabilities are auto-discovered via entry points. Built-in plugins have known descriptors; custom plugins can provide `PluginCapability` metadata. Orchestrator is always enabled when installed — no separate `enabled` flag needed.

---

## 📦 Package Distribution

The package is published to PyPI as `ghost-orchestrator`. Requires Ghostclaw ≥0.2.1b0 (install separately if not already).

---

## 🔧 Development

### Project Structure

```
ghostclaw-plugin-orchestrator/
├── src/ghost_orchestrator/
│   ├── __init__.py
│   ├── models.py           # Data classes
│   ├── vector_advisor.py   # QMD-based plugin ranking
│   ├── llm_planner.py      # LLM-based planning
│   ├── orchestrator.py     # Main engine
│   └── plugin.py           # Ghostclaw plugin wrapper
├── tests/
│   └── test_orchestrator.py
├── pyproject.toml
└── README.md
```

### Running Tests

```bash
cd plugins/ghostclaw-plugin-orchestrator
pytest tests/ -v
# 7 tests: config validation, models, orchestrator creation, plan generation, fallback
```

### Manual Testing

```bash
# Quick smoke test
python3 -c "
from ghost_orchestrator.plugin import OrchestratorPlugin
import asyncio

plugin = OrchestratorPlugin(config={})
result = asyncio.run(plugin.analyze('/path/to/repo', []))
print('Selected:', result.get('red_flags'))
print('Plan:', result.get('metadata', {}).get('orchestrator_plan'))
"
```

---

## 📊 Current Status

**Phase:** Pre-PyPI Release (2026-03-21)

| Feature | Status |
|---------|--------|
| Plugin discovery via entry points | ✅ Done |
| VectorAdvisor with QMD + heuristic fallback | ✅ Done |
| LLMPlanner (OpenRouter/OpenAI) | ✅ Done |
| Orchestrator engine (plan → execute) | ✅ Done |
| Ghostclaw plugin wrapper | ✅ Done |
| QMD store integration | ✅ Done |
| Repository profiling (languages, frameworks, git) | ✅ Done |
| Plugin capability descriptors | ✅ Done |
| Result deduplication | ✅ Done |
| Parallel plugin execution | ✅ Done |
| Plan caching | ✅ Done |
| Detailed metrics (latency, cache hit, qmd_hit) | ✅ Done |
| Benchmark framework | ✅ Done (scripts ready) |
| Packaging & publishing | ✅ Done (built, validated) |

> **Note:** Orchestrator loads and runs selected plugins via entry points. Results are merged, deduplicated, and annotated with metrics.

---

## 🔮 Roadmap

### Already Implemented (v0.1.0a1)
- See status table above — all core features are complete.

### Future Enhancements
- [ ] Benchmark on diverse repos to quantify impact (plugin reduction, coverage)
- [ ] Tune LLM prompts and add cost tracking
- [ ] Consider collaborative filtering or reinforcement learning
- [ ] Possibly integrate into Ghostclaw core (if evaluation positive)

---

## 🧪 Research Questions

---

## 🧪 Research Questions

1. **Effectiveness:** Does orchestration reduce plugin count without missing important issues?
2. **Speed:** What's the latency improvement? (Planning cost vs execution savings)
3. **QMD value:** Is vector similarity actually predictive, or are heuristics enough?
4. **LLM vs heuristic:** Is the added LLM cost worth it for plan quality?
5. **Cold start:** How does it behave on repos with no QMD history?

We'll measure by:
- Running baseline (all plugins) vs orchestrated (selected subset) on same repos
- Comparing issue sets (precision/recall)
- Timing each plugin execution
- Tracking QMD hit rates

---

## 🤝 Contributing

This is an experimental module. If you'd like to help:

1. **Try it** on your own repos and report findings
2. **Implement** missing pieces (see Roadmap)
3. **Benchmark** and compare strategies
4. **Suggest** better heuristics or advisor algorithms

Guidelines:
- Keep changes isolated to `orchestrator/`
- Write tests for new features
- Update this README and `CHANGELOG.md` (to be created)
- Follow Ghostclaw's coding style (black, ruff, mypy)

---

## 📚 See Also

- **Ghostclaw Plugin System:** `../plugins/README.md`
- **QMD Documentation:** (coming soon)
- **Ghostclaw Core:** https://github.com/ghostclaw/ghostclaw-core

---

## 📝 License

MIT — same as Ghostclaw core.

---

**Status:** Experimental — may change or be removed without notice.
