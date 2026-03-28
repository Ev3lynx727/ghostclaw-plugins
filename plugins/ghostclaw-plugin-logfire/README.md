# Ghostclaw Plugin: Logfire

Analyzes Python codebases for [Pydantic Logfire](https://logfire.pydantic.dev) observability integration.

## Features

- **Configuration Analysis** — Detects if Logfire is properly configured
- **Instrumentation Coverage** — Identifies un-instrumented packages (FastAPI, SQLAlchemy, etc.)
- **Pattern Detection** — Finds best practices and anti-patterns
- **Security Scanning** — Flags hardcoded tokens/API keys

## Installation

```bash
cd ghostclaw-plugin-logfire
pip install -e .
```

## Usage

```bash
# With auto-discovery
cd /your/repo
ghostclaw analyze . --no-ai

# Or manually
ghostclaw analyze . --plugins logfire
```

## Configuration

Add to `.ghostclaw.json` or `opencode.jsonc`:

```json
{
  "mcp": {
    "plugins": {
      "logfire": {
        "check_config": true,
        "check_instrumentation": true,
        "required_integrations": ["fastapi", "sqlalchemy"]
      }
    }
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `check_config` | bool | `true` | Check for proper `logfire.configure()` setup |
| `check_instrumentation` | bool | `true` | Check for `instrument_*()` coverage |
| `required_integrations` | list | `[]` | List of integrations that must be instrumented |

## Detected Issues

### Configuration Issues

| Rule ID | Severity | Description |
|---------|----------|-------------|
| `LOGFIRE_NOT_CONFIGURED` | high | Logfire imported but `configure()` not called |
| `LOGFIRE_LOCAL_MODE` | info | Running with `send_to_logfire=False` |

### Instrumentation Issues

| Rule ID | Severity | Description |
|---------|----------|-------------|
| `LOGFIRE_UNINSTRUMENTED_PACKAGE` | medium | Package imported but not instrumented |
| `LOGFIRE_MISSING_INTEGRATION` | medium | Required integration not found |

### Pattern Issues

| Rule ID | Severity | Description |
|---------|----------|-------------|
| `LOGFIRE_EMPTY_SPAN_NAME` | low | Span created with empty name |

### Security Issues (Red Flags)

| Rule ID | Severity | Description |
|---------|----------|-------------|
| Hardcoded Token | critical | API key/token found in source code |

## Supported Instrumentations

The plugin detects these Logfire instrumentations:

- `instrument_fastapi`
- `instrument_django`
- `instrument_flask`
- `instrument_sqlalchemy`
- `instrument_httpx`
- `instrument_requests`
- `instrument_openai`
- `instrument_anthropic`
- `instrument_asyncpg`
- `instrument_redis`
- `instrument_celery`
- `instrument_pydantic_ai`
- `instrument_sqlite3`
- `instrument_psycopg`
- `instrument_pymongo`
- `instrument_structlog`
- `instrument_loguru`

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linting
ruff check src/
black --check src/
```

## License

MIT
