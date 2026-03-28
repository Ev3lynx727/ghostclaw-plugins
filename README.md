# Ghostclaw Experimental — Side-Project Workspace

**Status:** Active — plugin prototyping zone  
**Parent:** `ghostclaw` core (separate repo)

---

## 📦 Contents

### Templates

- `plugins/plugin-template/` — Generic boilerplate for any Ghostclaw plugin
  - Complete `pyproject.toml` with entry points
  - Example `plugin.py` inheriting from `PluginBase`
  - Tests and README
  - Ready to copy and customize

### Example Plugins (Working Prototypes)

- **`ghostclaw-plugin-bandit/`** — Bandit Python security scanner integration
  - Runs `bandit -r -f json`, parses findings
  - Returns issues as formatted strings with file:line, severity, description
  - Includes README, tests, and pyproject.toml

- **`ghostclaw-plugin-coderabbit/`** — CodeRabbit AI code review integration
  - Runs `coderabbit review --plain --no-color --type all`
  - Auto-detects base branch to avoid git diff errors
  - Parses plain-text output into structured Ghostclaw issues
  - Requires `CODERABBIT_API_KEY` environment variable
  - Handles rate limits and errors gracefully

**Create your own:** Copy `templates/plugin-template/` and customize!

---

## 📚 Documentation

See **[PLUGINS.md](PLUGINS.md)** for comprehensive guides on:

- Plugin architecture and structure
- Two discovery methods (pip entry points vs local copy)
- Step-by-step development workflow
- CI/CD integration examples
- Troubleshooting tips

Quick commands:

```bash
# Scaffold a new plugin
ghostclaw plugins scaffold myplugin   # creates .ghostclaw/plugins/myplugin/

# Install a plugin for global/pip-based discovery
cd plugins/ghostclaw-plugin-coderabbit
pip install -e .

# List discovered plugins
ghostclaw plugins list

# Test a plugin
ghostclaw plugins test coderabbit

# Run analysis (plugins auto-discovered)
cd /your/repo
ghostclaw analyze . --no-ai
```

---

## 🛠️ Skills & Workflow

- `.agents/skills/plugins-builder/SKILL.md` — describes how to scaffold new plugins
- `.agents/workflow.md` — step-by-step guide: ideate → scaffold → implement → test → share
- `AGENTS.md` — side-project rules, memory conventions, scope boundaries

---

## 🧪 How to Use

### Start a new plugin

```bash
# Option 1: Copy template manually
cp -r plugins/plugin-template ghostclaw-plugin-mytool
# Then edit files (rename package, implement analyze())

# Option 2: Use the plugins-builder skill (if integrated in your agent)
# Say: "create a ghostclaw plugin named ghostclaw-plugin-mytool"
```

### Test a plugin

```bash
cd plugins/ghostclaw-plugin-mytool
pip install -e .
ghostclaw analyze /path/to/repo --plugins ghostclaw-plugin-mytool
```

### Share

- Push to GitHub (public or private)
- Optionally publish to PyPI
- Announce in Ghostclaw discussions

---

## 📝 Memory

Daily logs: `memory/YYYY-MM-DD.md`  
Long-term: `MEMORY.md` (create if needed)

---

## 🎯 Mission

Seed the Ghostclaw plugin ecosystem with practical integrations:

- Security (Bandit, Semgrep)
- Quality (CodeRabit, Pylint, Radon)
- Compliance (OWASP, SPDX SBOM)
- Custom analyses (company-specific rules)

**Keep plugins focused, composable, and independent.**
