# Workflow: Creating a Ghostclaw Plugin

**For:** `ghostclaw-experimental` side-project workspace  
**Goal:** Rapidly build, test, and iterate on plugin ideas

---

## Step 1: Ideation

Identify the external tool or feature you want to integrate:
- Security scanner (bandit, semgrep)
- Code quality (coderabit, pylint, radon)
- Documentation generator
- Custom analyzer (your own logic)

**Question:** Does it extend Ghostclaw's analysis capabilities? If yes → good plugin.

---

## Step 2: Scaffold

Use the `plugins-builder` skill to create the template:
```
create a ghostclaw plugin named ghostclaw-plugin-<name>
```

This generates:
```
ghostclaw-plugin-<name>/
├── README.md
├── pyproject.toml
├── src/
│   └── ghostclaw_plugin_<name>/
│       ├── __init__.py
│       ├── plugin.py       # main plugin class
│       └── analyzer.py     # optional: custom analyzer logic
├── tests/
│   └── test_plugin.py
└── .ghostclaw/ (optional)  # plugin-specific config
```

---

## Step 3: Implement

Flesh out the plugin:

### `plugin.py` — Entry point
```python
from ghostclaw import PluginBase

class BanditPlugin(PluginBase):
    name = "bandit"
    version = "0.1.0"

    def analyze(self, repo_path, config):
        # Run bandit, parse results, return findings
        pass

    def report(self, findings):
        # Format findings for Ghostclaw storage
        pass
```

### `analyzer.py` (optional)
Custom analysis logic that doesn't wrap an external tool.

---

## Step 4: Test Locally

```bash
cd ghostclaw-plugin-<name>
pip install -e .
# In a separate repo with Ghostclaw installed:
ghostclaw analyze . --plugins ghostclaw-plugin-<name>
```

Check that plugin appears in output and runs without errors.

---

## Step 5: Iterate

- Add more analysis features
- Improve error handling
- Add config options
- Write more tests
- Document usage in README

---

## Step 6: Share

Options:
- Keep it local (just for your own use)
- Publish to PyPI (if generally useful)
- Share as GitHub repo (community-maintained)
- List in Ghostclaw's plugin registry (if we create one)

**Tagging:** `ghostclaw-plugin-*` naming convention helps discoverability.

---

## Quick Tips

- Keep plugins **single-purpose** — one tool per plugin
- Respect Ghostclaw's architecture-first philosophy — plugins should enhance architectural understanding, not just report linter warnings
- Use Ghostclaw's `PluginBase` API for consistency
- Don't depend on unreleased core features unless clearly marked as experimental

---

**Remember:** Plugins are side-projects. They evolve independently. Core Ghostclaw will never depend on them.
