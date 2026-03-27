# Ghostclaw Experimental Plugins

This directory contains example Ghostclaw plugins demonstrating the plugin system and auto-discovery via setuptools entry points.

## Available Plugins

### 1. Bandit Plugin (`ghostclaw-plugin-bandit/`)
Integrates [Bandit](https://github.com/PyCQA/bandit) — a Python security scanner — into Ghostclaw.

**Features:**
- Runs `bandit -r -f json` on the repository
- Normalizes findings into Ghostclaw issues
- Requires `bandit` CLI installed

**Installation:**
```bash
cd ghostclaw-plugin-bandit
pip install -e .
```

**Usage:**
```bash
# With auto-discovery (Ghostclaw ≥0.2.1 with entry point support)
cd /your/repo
ghostclaw analyze . --no-ai

# Or manually copy to .ghostclaw/plugins/
mkdir -p .ghostclaw/plugins
cp -r /path/to/ghostclaw-plugin-bandit .ghostclaw/plugins/
```

---

### 2. CodeRabbit Plugin (`ghostclaw-plugin-coderabbit/`)
Integrates [CodeRabbit](https://coderabbit.ai) AI-powered code review into Ghostclaw.

**Features:**
- Runs `coderabbit review --plain --no-color --type all`
- Auto-detects base branch (`main`/`master`) to avoid git diff errors
- Parses plain-text output into structured Ghostclaw findings
- Requires `CODERABBIT_API_KEY` environment variable

**Installation:**
```bash
cd ghostclaw-plugin-coderabbit
pip install -e .
```

**Usage:**
```bash
export CODERABBIT_API_KEY="your-key-here"
cd /your/repo
ghostclaw analyze . --no-ai
```

---

## Plugin Discovery Methods

Ghostclaw supports **two** ways to make plugins available:

### Method A: Pip Installation + Entry Points (Recommended for CI/CD)

1. **Install the plugin package** anywhere on the system (global, venv, or user site):
   ```bash
   pip install ghostclaw-plugin-coderabbit
   ```

2. **Run Ghostclaw** — plugins are auto-discovered via setuptools entry points:
   ```bash
   ghostclaw plugins list  # shows installed plugins
   ghostclaw analyze .     # uses them automatically
   ```

No manual copying required. Works in any repository, fresh or existing.

### Method B: Local Copy to `.ghostclaw/plugins/` (Legacy)

1. Copy the plugin directory into the repository:
   ```bash
   cp -r /path/to/ghostclaw-plugin-coderabbit /your/repo/.ghostclaw/plugins/
   ```

2. Run Ghostclaw in that repo:
   ```bash
   cd /your/repo
   ghostclaw analyze .
   ```

This method allows per-repo plugin versioning but requires manual copying.

---

## How Auto-Discovery Works

When Ghostclaw starts (via `PluginService.initialize_registry()`), it:

1. Registers built-in plugins (pyscn, ai-codeindex, sqlite, qmd, json_target, lizard)
2. Calls `PluginRegistry.load_external_plugins()`, which:
   - Scans `.ghostclaw/plugins/` if it exists and loads plugins from there
   - **Also** calls `self.pm.load_setuptools_entrypoints("ghostclaw.plugins")` to discover any installed `ghostclaw-plugin-*` packages
   - Instantiates plugin classes automatically
   - Deduplicates (local plugins take precedence over entry points with same name)
   - Populates `external_plugins` set for Type display in `ghostclaw plugins list`

**Result:** Any package that defines an entry point in `pyproject.toml`:
```toml
[project.entry-points."ghostclaw.plugins"]
myplugin = "my_plugin_module:MyPluginClass"
```
is automatically available after `pip install`.

---

## Plugin Structure

A minimal Ghostclaw plugin:

```
my-plugin/
├── pyproject.toml
├── README.md
├── src/
│   └── my_plugin_package/
│       ├── __init__.py
│       └── plugin.py
└── tests/
    └── test_plugin.py
```

**pyproject.toml** key parts:
```toml
[project]
name = "ghostclaw-plugin-myplugin"
version = "0.1.0"
description = "Description"
readme = "README.md"
requires-python = ">=3.9"
dependencies = ["ghostclaw>=0.2.0"]

[project.entry-points."ghostclaw.plugins"]
myplugin = "my_plugin_package.plugin:MyPluginClass"
```

**plugin.py** must implement `MetricAdapter` or another adapter base:
```python
from ghostclaw.core.adapters.base import MetricAdapter, AdapterMetadata
from ghostclaw.core.adapters.hooks import hookimpl

class MyPluginClass(MetricAdapter):
    def get_metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            name="myplugin",
            version="0.1.0",
            description="My plugin description"
        )

    async def is_available(self) -> bool:
        # Check external dependency
        return True

    async def analyze(self, root: str, files: List[str]) -> Dict[str, Any]:
        # Do work, return dict with issues, architectural_ghosts, red_flags
        return {"issues": [], "architectural_ghosts": [], "red_flags": []}

    @hookimpl
    async def ghost_analyze(self, root: str, files: List[str]) -> Dict[str, Any]:
        # Called by Ghostclaw; delegate to analyze()
        return await self.analyze(root, files)

    @hookimpl
    def ghost_get_metadata(self) -> Dict[str, Any]:
        meta = self.get_metadata()
        return {"name": meta.name, "version": meta.version, "description": meta.description}
```

See `ghostclaw-plugin-bandit/` and `ghostclaw-plugin-coderabbit/` for complete working examples.

---

## Testing Plugins

### Run unit tests
```bash
cd ghostclaw-plugin-coderabbit
pytest tests/
```

### Test with Ghostclaw CLI
```bash
# Install plugin
pip install -e .

# Verify discovery
ghostclaw plugins list
ghostclaw plugins test myplugin

# Run analysis in a test repo
cd /some/repo
ghostclaw analyze . --no-ai --verbose
```

---

## CI/CD Integration

In your CI pipeline (GitHub Actions, GitLab CI, etc.):

```yaml
- name: Install Ghostclaw and plugins
  run: |
    pip install ghostclaw
    pip install ghostclaw-plugin-coderabbit  # or bandit, etc.

- name: Run analysis
  env:
    CODERABBIT_API_KEY: ${{ secrets.CODERABBIT_API_KEY }}
  run: |
    ghostclaw analyze . --no-ai
```

No need to copy plugin directories — pip install handles it.

---

## Troubleshooting

### Plugin not showing in `ghostclaw plugins list`
- Ensure it's installed: `pip list | grep ghostclaw-plugin`
- Check entry point in `pyproject.toml` is correct
- Make sure the plugin class is importable: `python -c "import my_plugin_package.plugin; print('OK')"`
- Verify Ghostclaw version includes the entry point auto-discovery feature (≥0.2.1)

### Plugin loads but `is_available()` returns False
- Check external dependency is installed and in PATH (e.g., `coderabbit --version`, `bandit --version`)
- Verify environment variables (e.g., `CODERABBIT_API_KEY`) are set

### Analysis errors: "table reports has no column named..."
- The SQLite database schema is outdated. Delete `.ghostclaw/` and re-run analysis to recreate with current schema.

---

## Contributing

Feel free to fork and add new plugins! Follow the structure above. Add tests, a README, and submit PRs to the main Ghostclaw repository if you'd like to share them as official plugins.

Happy hacking! 🦾
