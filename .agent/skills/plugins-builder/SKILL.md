---
name: plugins-builder
description: Scaffold, test, and package Ghostclaw plugins quickly and consistently.
---

# plugins-builder Skill

**Purpose:** Scaffold, test, and package Ghostclaw plugins quickly and consistently.

## What It Does

- Creates standardized plugin project structure
- Boilerplate code for plugin API integration
- Configuration templates (pyproject.toml, setup.cfg)
- Example plugin implementations to copy
- Validation and linting for plugin quality

## Triggers

Any of these phrases:
- "create a ghostclaw plugin"
- "scaffold a plugin"
- "new plugin from template"
- "plugin builder"
- "ghostclaw plugin template"

## Usage Pattern

When triggered, this skill:
1. Asks for plugin name (e.g., `ghostclaw-plugin-bandit`)
2. Creates directory structure with boilerplate
3. Populates files from templates
4. Explains how to develop/test the plugin
5. Shows next steps (install, configure, share)

## Output

- New plugin project directory with complete structure
- README.md with usage instructions
- Example plugin code (minimal working example)
- pyproject.toml with dependencies
- Linting/config files
- test/ directory with sample tests

## Notes

- Plugins are independent packages, not part of core Ghostclaw
- They can be published to PyPI or kept local
- This skill only creates structure; implementation depends on plugin type
