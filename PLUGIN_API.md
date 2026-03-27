# Ghostclaw Plugin API Reference

This document serves as an extended reference for the Ghostclaw Plugin API. For a quick start, please see `CONTRIBUTING.md`.

## Lifecycle of a Plugin

Ghostclaw utilizes **Pluggy** for its plugin system. The core engine defines several `hookspecs` that your plugin can implement via `@hookimpl`.

When a user runs `ghostclaw analyze`:
1. Ghostclaw uses `pkg_resources` (entry points) to dynamically load installed plugins under the `ghostclaw.plugins` namespace.
2. The core checks the `@hookimpl` `ghost_get_metadata()` method on all discovered plugins.
3. It filters out disabled plugins (via config) or unavailable plugins.
4. During the **Metrics Collection Phase**, Ghostclaw concurrently calls the `@hookimpl` `ghost_analyze(root, files, config, **kwargs)` hook across all active plugins.
5. The resulting metric dictionaries are merged into the final universal JSON schema.

## Base Classes

You should rarely implement hooks completely from scratch. Use the provided base adapters:

### `AsyncProcessMetricAdapter`
Ideal for wrappers around external CLI tools (e.g. Bandit, Semgrep, CodeRabbit).
- Provides the `self.run_tool(cmd, timeout=30)` async utility.
- Automatically handles basic subprocess timeouts and non-zero exit codes.

### `MetricAdapter`
Ideal for pure Python analysis (e.g. AST parsing, static regex scanning).
- Fully synchronous or asynchronous interface depending on your overrides.

## The Return Dictionary

Every plugin's `analyze` method must return a `Dict[str, Any]` containing exactly these three keys (they can be empty lists):

```python
{
    "issues": [ ... ],
    "architectural_ghosts": [ ... ],
    "red_flags": [ ... ]
}
```

### 1. Issues (The Granular Findings)
Issues are specific occurrences connected to lines of code.

**Legacy Support:** List of strings (e.g., `["path/to/file.py:10 - Found bug"]`).
**Rich Standard (Preferred):** List of dictionaries:
```python
{
    "rule_id": "BANDIT_B201",
    "title": "A brief title",
    "message": "Detailed description of the bug.",
    "severity": "high",  # Must be: critical, high, medium, low, info
    "file_path": "/absolute/path/or/relative",
    "line_start": 42,
    "line_end": 42,
    "metadata": {"custom_data": True}
}
```

### 2. Architectural Ghosts
Higher-level, systemic inferences. E.g. "The system has multiple conflicting logging setups across folders."
- Must be a `List[str]`.

### 3. Red Flags
Meta-errors about the plugin execution itself.
- E.g. "Failed to allocate memory for parsing X" or "API token missing for Coderabbit".
- Must be a `List[str]`.

## Configuration Options

Plugins can natively receive their specific configurations through the core argument `config: Optional[Dict[str, Any]] = None`.

A project's `.ghostclaw.json` or `opencode.jsonc` can define:
```json
{
  "mcp": {
    "plugins": {
      "bandit": {
        "exclude_paths": ["tests", "docs"],
        "severity_threshold": "medium"
      }
    }
  }
}
```
If your adapter is named `"bandit"`, this nested config object is passed seamlessly to your `analyze()` entry point.
