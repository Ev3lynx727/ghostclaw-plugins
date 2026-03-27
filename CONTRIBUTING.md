# Contributing — Ghostclaw Plugins

Welcome! This guide helps you create and maintain Ghostclaw plugins.

---

## 🎯 What is a Plugin?

A plugin extends Ghostclaw's analysis capabilities by:
- Running external tools (security scanners, linters, metrics)
- Formatting results into the standard Ghostclaw report schema
- Optionally adding configuration options

Plugins are **independent packages** that live outside the core Ghostclaw repo. They can be:
- Published to PyPI (e.g., `ghostclaw-plugin-bandit`)
- Kept local in `.ghostclaw/plugins/`
- Distributed via GitHub

---

## 📦 Plugin Structure

Ghostclaw plugins are **single-package modules** with the following layout:

```
ghostclaw-plugin-<name>/
├── README.md
├── pyproject.toml
├── src/
│   └── ghostclaw_plugin_<name>/
│       ├── __init__.py   # <-- Plugin class defined here
│       └── analyzer.py   # (optional) separate analysis logic
└── tests/
    └── test_plugin.py
```

**Important:** The entry point in `pyproject.toml` must point to the plugin class. If the class is defined directly in `__init__.py`, use:

```toml
[project.entry-points."ghostclaw.plugins"]
myplugin = "ghostclaw_plugin_<name>:MyPluginClass"
```

If you split the class into a separate module (e.g., `plugin.py` or `analyzer.py`), adjust the path accordingly: `ghostclaw_plugin_<name>.plugin:MyPluginClass`.

Both patterns are supported; the simplest is to define the class in `__init__.py`.

---

## 🔌 Plugin API

Your plugin class must inherit from `AsyncProcessMetricAdapter` (for subprocess-based tools) or `MetricAdapter` (for pure-Python analyzers). Implement these methods:

```python
from ghostclaw.core.adapters.metric.base import AsyncProcessMetricAdapter
from ghostclaw.core.adapters.base import AdapterMetadata
from ghostclaw.core.adapters.hooks import hookimpl
from typing import Dict, List, Any

class MyPlugin(AsyncProcessMetricAdapter):

    def get_metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            name="myplugin",
            version="0.1.0",
            description="What this plugin does",
            dependencies=["external-tool"]  # optional
        )

    async def is_available(self) -> bool:
        """Check if the external tool is installed and callable."""
        result = await self.run_tool(["mytool", "--version"])
        return result.get("returncode") == 0

    async def analyze(self, root: str, files: List[str]) -> Dict[str, Any]:
        """
        Main analysis logic.

        Args:
            root: Repository root path (str)
            files: List of file paths to analyze (List[str])

        Returns:
            Dict with keys: 'issues', 'architectural_ghosts', 'red_flags'.
            - issues: List[str] (human-readable messages)
            - architectural_ghosts: List[str]
            - red_flags: List[str]
        """
        # Build command, run it via self.run_tool()
        # Process results into lists of strings
        return {
            "issues": [...],          # List of issue messages
            "architectural_ghosts": [...],
            "red_flags": [...]
        }

    @hookimpl
    async def ghost_analyze(self, root: str, files: List[str]) -> Dict[str, Any]:
        """Ghostclaw hook — forwards to analyze()."""
        return await self.analyze(root, files)

    @hookimpl
    def ghost_get_metadata(self) -> Dict[str, Any]:
        """Ghostclaw hook — returns plugin metadata."""
        meta = self.get_metadata()
        return {
            "name": meta.name,
            "version": meta.version,
            "description": meta.description,
            "available": True  # or dynamic check
        }
```

### Return Format

- **`issues`**: Your primary findings as **strings** (e.g., `"path/to/file.py:10 - SEC001: Hardcoded password"`) or as list of dicts with keys `rule_id`, `title`, `message`, `severity`, `file_path`, `line_start`, `line_end`, `metadata`. See examples.
- `architectural_ghosts`: Higher-level insights (list of strings) (e.g., `"Found 3 circular dependencies"`)
- `red_flags`: Critical warnings (list of **strings**). Note: must be strings, not dicts.

All three keys must be present in the returned dict (empty lists if none).

---

## 🛠️ Development Workflow

1. **Use the `plugins-builder` skill** (if using an AI assistant) OR **Copy the template** from `plugins/plugin-template/`
2. **Rename the package** (`ghostclaw_plugin_template` → `ghostclaw_plugin_<name>`)
3. **Implement** your adapter class in `__init__.py`
4. **Update `pyproject.toml`** with your plugin name, dependencies, and entry point
5. **Test locally**:
   ```bash
   pip install -e .
   cp -r src/ghostclaw_plugin_<name> /path/to/test/project/.ghostclaw/plugins/
   ghostclaw analyze /path/to/test/project --no-ai
   ```
6. **Write unit tests** (mock `self.run_tool` for subprocess plugins)
7. **Document** usage in README.md
8. **Share** (GitHub, PyPI, or keep local)

---

## 📝 Configuration (Advanced)

If your plugin needs user configuration, you have multiple options:

1. **Directly via Ghostclaw** — The `ghost_analyze` hook accepts a `config` keyword argument dict containing user settings.
2. **Environment variables** — Read `os.getenv("GHOSTCLAW_MYPLUGIN_X")`
3. **Project config** — Have users create `.ghostclaw/plugins/myplugin/config.json` in their repo

Example reading a local config:

```python
import json
from pathlib import Path

async def analyze(self, root: str, files: List[str]) -> Dict[str, Any]:
    config_path = Path(root) / ".ghostclaw" / "plugins" / "bandit" / "config.json"
    exclude = []
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text())
            exclude = cfg.get("exclude", [])
        except Exception:
            pass

    cmd = ["bandit", "-r", "-f", "json"]
    if exclude:
        cmd.extend(["-x", ",".join(exclude)])
    cmd.append(root)
    # ...
```

---

## 🧪 Testing

Use `pytest` and mock `self.run_tool`:

```python
from unittest.mock import patch, AsyncMock
import pytest

@pytest.mark.asyncio
async def test_analyze_success():
    plugin = MyPlugin()
    mock_result = {"returncode": 0, "stdout": '{"results": []}', "stderr": ""}
    with patch.object(plugin, "run_tool", new_callable=AsyncMock, return_value=mock_result):
        result = await plugin.analyze("/fake/repo", [])
    assert isinstance(result["issues"], list)
    # more assertions...
```

---

## 📦 Packaging

- Use `pyproject.toml` (PEP 621) with `setuptools`
- Entry point group: `ghostclaw.plugins` maps name → class path
- Install with `pip install -e .` for development
- Build with `python -m build`
- Upload to TestPyPI first: `twine upload --repository testpypi dist/*`

---

## 📢 Distribution & Discovery

Once your plugin is installed (via `pip install` or copied to `.ghostclaw/plugins/`), Ghostclaw automatically discovers it:

- **Pip install + entry points** (recommended for CI/CD): `pip install ghostclaw-plugin-foo` makes it available in any repo.
- **Local copy** (per-repo versioning): Copy the plugin directory to `.ghostclaw/plugins/` in the repository.

Ensure your `pyproject.toml` includes the `ghostclaw.plugins` entry point; this is what Ghostclaw scans.

---

## 🎉 Example Plugins

- `ghostclaw-plugin-bandit` — Bandit security scanner (reference implementation)
- `ghostclaw-plugin-coderabit` — Code quality/style (coming soon)

Study their source for patterns.

---

## ❓ Need Help?

- Open an issue in the Ghostclaw core repo
- Ask in Discord: https://discord.com/invite/clawd
- Read core adapter code in `src/ghostclaw/core/adapters/`

---

**Happy plugin building!** 🚀
