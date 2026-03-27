# Ghostclaw Bandit Plugin

Integrates [Bandit](https://github.com/PyCQA/bandit) security scanner into Ghostclaw's architecture analysis pipeline.

**Status:** Experimental prototype

---

## What It Does

- Runs Bandit recursively on Python files in your repository
- Imports security findings into Ghostclaw's memory
- Reports issues with severity, confidence, and line numbers
- **Automatically excludes** `.ghostclaw/plugins/` to avoid self-reporting

---

## Installation

```bash
# From the plugin directory
pip install -e .

# Or from PyPI (when published)
pip install ghostclaw-plugin-bandit
```

---

## Usage

### As a standalone plugin
```bash
ghostclaw analyze /path/to/your/repo --plugins bandit
```

### Via config (recommended)
Add to `.ghostclaw/ghostclaw.json` in your project:
```json
{
  "plugins": ["bandit"]
}
```
Then run normally:
```bash
ghostclaw analyze .
```

---

## Output

Findings are stored in Ghostclaw's memory and searchable via:
```bash
ghostclaw memory-search "bandit HIGH severity"
```

Each issue is formatted as:
```
path/to/file.py:10 - B101 (LOW): Use of assert detected.
```

---

## Future Enhancements

- [ ] Custom exclude paths (beyond default `.ghostclaw/plugins`)
- [ ] Threshold filtering (min severity/confidence)
- [ ] SARIF output option
- [ ] CI mode (exit code based on findings)
- [ ] Support for custom Bandit profiles

---

## License

```bash
cd ghostclaw-experimental/ghostclaw-plugin-bandit
pip install -e ".[dev]"
pytest
```

For local testing in a separate project:
```bash
# In the project you want to scan
mkdir -p .ghostclaw/plugins
cp -r /path/to/ghostclaw-plugin-bandit/src/ghostclaw_plugin_bandit .ghostclaw/plugins/
ghostclaw analyze . --no-ai
```

---

## Future Enhancements

- [ ] Threshold filtering (min severity/confidence)
- [ ] SARIF output option
- [ ] CI mode (exit code based on findings)
- [ ] Configurable exclude via core config instead of separate file
- [ ] Support for custom Bandit profiles

---

## License

MIT (same as Ghostclaw core)

---

## Related

- Ghostclaw core: https://github.com/ghostclaw/ghostclaw
- Bandit: https://github.com/PyCQA/bandit
- Plugin Contributing: `CONTRIBUTING.md` in this workspace
