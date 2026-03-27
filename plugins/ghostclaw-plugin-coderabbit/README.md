# Ghostclaw Plugin: Coderabbit

Integrates the CodeRabbit AI code review CLI directly into Ghostclaw's analysis pipeline.

## Specification & Requirements

This plugin expects the CodeRabbit CLI to be installed and available in the system PATH.
- **CLI Dependency**: `coderabbit >= 0.3.0`
- **Authentication**: Requires the `CODERABBIT_API_KEY` environment variable to be set.
- **Output Parsing**: The plugin parses the plain text format output from `coderabbit review --plain --no-color --type all`. 
- **Branch Auto-Detection**: The plugin automatically detects the base comparison branch (preferring `main` or `master` if they are valid merge bases) to avoid comparison errors.

## Analysis Mapping

CodeRabbit findings are mapped to Ghostclaw standardized issues:
- `Type: security` / `error` -> Severity: **High**
- `Type: bug` / `performance` / `warning` -> Severity: **Medium**
- `Type: potential_issue` / `style` -> Severity: **Low**

If the external command times out (5 minutes max by default) or the API key is missing, Ghostclaw captures these as **Red Flags**.

## Usage

Ensure the CLI is installed and configured:
```bash
export CODERABBIT_API_KEY="your-key"
ghostclaw analyze .
```
