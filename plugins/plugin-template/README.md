# Ghostclaw Plugin Template

A starting point for building Ghostclaw plugins. This template follows Ghostclaw's plugin architecture with entry point auto-discovery.

## 🚀 Quick Start

1. **Copy the template:**
   ```bash
   cp -r templates/plugin-template ghostclaw-plugin-<name>
   ```

2. **Rename the package:**
   ```bash
   cd ghostclaw-plugin-<name>
   mv src/ghostclaw_plugin_template src/ghostclaw_plugin_<name>
   ```

3. **Update `pyproject.toml`:**
   - `name = "ghostclaw-plugin-<name>"`
   - `description`, `authors`, etc.
   - Entry point: change `template` to `<name>` and module path to match your package
   - Add any dependencies (e.g., external tools like `bandit`)

4. **Implement your plugin** in `src/ghostclaw_plugin_<name>/__init__.py`:
   - Rename `TemplatePlugin` to something meaningful (e.g., `MyPlugin`)
   - Update `get_metadata().name` to match your plugin name
   - Fill in `is_available()` and `analyze()` logic

5. **Install locally:**
   ```bash
   pip install -e .
   ```

6. **Test:**
   ```bash
   # From any repo (plugins auto-discovered via entry points)
   cd /path/to/repo
   ghostclaw plugins list                # should show your plugin
   ghostclaw analyze . --no-ai --verbose
   ```

## 📁 Directory Layout

```
ghostclaw-plugin-<name>/
├── README.md           # Your plugin's documentation
├── pyproject.toml      # Package metadata and dependencies
├── src/
│   └── ghostclaw_plugin_<name>/
│       ├── __init__.py   # Plugin class defined here
│       └── analyzer.py   # Optional: separate analysis helpers
└── tests/
    └── test_plugin.py  # Unit tests
```

## 🔧 Plugin API

Your plugin class should inherit from `AsyncProcessMetricAdapter` (for subprocess-based tools) or `MetricAdapter` (for pure-Python analyzers). At minimum, implement:

```python
from ghostclaw.core.adapters.metric.base import AsyncProcessMetricAdapter
from ghostclaw.core.adapters.base import AdapterMetadata
from ghostclaw.core.adapters.hooks import hookimpl
from typing import Dict, List, Any

class MyPlugin(AsyncProcessMetricAdapter):

    def get_metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            name="<name>",
            version="0.1.0",
            description="What this plugin does",
            dependencies=["external-tool"]  # optional
        )

    async def is_available(self) -> bool:
        """Check if external tool is installed and callable."""
        result = await self.run_tool(["mytool", "--version"])
        return result.get("returncode") == 0

    async def analyze(self, root: str, files: List[str]) -> Dict[str, Any]:
        """
        Main analysis logic.

        Args:
            root: Repository root path (str)
            files: List of file paths to analyze (List[str])

        Returns:
            Dict with keys:
                - 'issues': List[str] or List[dict] (primary findings)
                - 'architectural_ghosts': List[str] (higher-level insights)
                - 'red_flags': List[str] (critical warnings)
        """
        # Use self.run_tool() for subprocess execution
        result = await self.run_tool(["mytool", "--format", "json", root])
        # Parse result['stdout'] and build output
        return {
            "issues": [...],
            "architectural_ghosts": [...],
            "red_flags": [...]
        }

    @hookimpl
    async def ghost_analyze(self, root: str, files: List[str], config: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Ghostclaw hook — called during analysis."""
        return await self.analyze(root, files, config=config, **kwargs)

    @hookimpl
    def ghost_get_metadata(self) -> Dict[str, Any]:
        """Ghostclaw hook — returns metadata for listing."""
        meta = self.get_metadata()
        return {
            "name": meta.name,
            "version": meta.version,
            "description": meta.description,
            "available": True  # or dynamic check
        }
```

### Return Types

- **issues**: Either list of strings (simple messages) or list of dicts with keys:
  `rule_id`, `title`, `message`, `severity` (`critical`, `high`, `medium`, `low`, `info`), `file_path`, `line_start`, `line_end`, `metadata` (optional). Using dicts provides richer data for downstream tools.
- `architectural_ghosts`: List of strings (e.g., `"Found circular dependencies between modules A and B"`)
- `red_flags`: List of **strings** — severe issues that block analysis or require immediate attention (e.g., `"CODERABBIT_MISSING_API_KEY: API key not set"`)

## 🧪 Testing

Use `pytest` and mock `self.run_tool` for subprocess plugins:

```python
import pytest
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_analyze():
    plugin = MyPlugin()
    mock_result = {"returncode": 0, "stdout": '{"findings": []}', "stderr": ""}
    with patch.object(plugin, "run_tool", new_callable=AsyncMock, return_value=mock_result):
        result = await plugin.analyze("/fake/repo", [])
    assert isinstance(result["issues"], list)
```

Run tests:
```bash
pytest tests/
```

## 📦 Packaging & Publishing

- `pyproject.toml` uses setuptools; entry point is `[project.entry-points."ghostclaw.plugins"]`
- Install dev: `pip install -e .`
- Build: `python -m build`
- Upload to TestPyPI first: `twine upload --repository testpypi dist/*`
- Then to PyPI: `twine upload dist/*`

Use `ghostclaw-plugin-*` naming convention for automatic discovery.

## 📚 More Info

See `../PLUGINS.md` in the `ghostclaw-experimental` workspace for comprehensive documentation on:
- Plugin discovery methods (pip entry points vs local copy)
- Development workflow
- CI/CD integration
- Troubleshooting

Happy hacking! 🛠️
