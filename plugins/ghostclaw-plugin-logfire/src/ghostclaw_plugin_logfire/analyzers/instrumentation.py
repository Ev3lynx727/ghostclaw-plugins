"""Instrumentation analyzer — checks for Logfire instrument_*() coverage."""

import ast
from pathlib import Path
from typing import Dict, List, Any, Set


# Known Logfire instrumentations and their corresponding packages
KNOWN_INSTRUMENTATIONS = {
    "fastapi": {"packages": ["fastapi"], "detect_import": "fastapi"},
    "django": {"packages": ["django"], "detect_import": "django"},
    "flask": {"packages": ["flask"], "detect_import": "flask"},
    "sqlalchemy": {"packages": ["sqlalchemy"], "detect_import": "sqlalchemy"},
    "httpx": {"packages": ["httpx"], "detect_import": "httpx"},
    "requests": {"packages": ["requests"], "detect_import": "requests"},
    "openai": {"packages": ["openai"], "detect_import": "openai"},
    "anthropic": {"packages": ["anthropic"], "detect_import": "anthropic"},
    "asyncpg": {"packages": ["asyncpg"], "detect_import": "asyncpg"},
    "redis": {"packages": ["redis"], "detect_import": "redis"},
    "celery": {"packages": ["celery"], "detect_import": "celery"},
    "pydantic_ai": {"packages": ["pydantic_ai"], "detect_import": "pydantic_ai"},
    "sqlite3": {"packages": ["sqlite3"], "detect_import": "sqlite3"},
    "psycopg": {
        "packages": ["psycopg", "psycopg2", "psycopg2cffi"],
        "detect_import": "psycopg",
    },
    "pymongo": {"packages": ["pymongo"], "detect_import": "pymongo"},
    "structlog": {"packages": ["structlog"], "detect_import": "structlog"},
    "loguru": {"packages": ["loguru"], "detect_import": "loguru"},
}


class InstrumentationAnalyzer:
    """Analyzes Logfire instrumentation coverage in Python files."""

    def __init__(self, root: str, files: List[str]):
        self.root = Path(root)
        self.files = [Path(f) for f in files]

    def analyze(self) -> Dict[str, Any]:
        """Run instrumentation coverage analysis."""
        issues: List[Dict[str, Any]] = []
        architectural_ghosts: List[str] = []

        # Track what's imported vs what's instrumented
        imported_packages: Set[str] = set()
        instrumented_packages: Set[str] = set()
        has_logfire = False

        for file_path in self.files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content, filename=str(file_path))
            except (SyntaxError, UnicodeDecodeError):
                continue

            visitor = InstrumentationVisitor()
            visitor.visit(tree)

            if visitor.has_logfire_import:
                has_logfire = True

            imported_packages.update(visitor.imported_packages)
            instrumented_packages.update(visitor.instrumented_calls)

        # Only report if logfire is actually used in the project
        if not has_logfire:
            return {"issues": [], "architectural_ghosts": []}

        # Find packages that are imported but not instrumented
        for pkg in imported_packages:
            if pkg in KNOWN_INSTRUMENTATIONS:
                instr_name = pkg
                if instr_name not in instrumented_packages:
                    issues.append(
                        {
                            "rule_id": "LOGFIRE_UNINSTRUMENTED_PACKAGE",
                            "title": f"Package '{pkg}' imported but not instrumented",
                            "message": f"The package '{pkg}' is imported but logfire.instrument_{instr_name}() "
                            f"was not called. Add instrumentation for full observability coverage.",
                            "severity": "medium",
                            "file_path": str(self.root),
                            "line_start": 0,
                            "line_end": 0,
                            "metadata": {
                                "package": pkg,
                                "instrumentation": f"instrument_{instr_name}",
                            },
                        }
                    )

        # Check for instrument_* calls that don't match any imported packages
        for instr in instrumented_packages:
            if instr not in KNOWN_INSTRUMENTATIONS:
                # Could be a custom or unknown instrumentation — just informational
                pass

        # Architectural ghost: large codebase with minimal instrumentation
        if len(imported_packages) > 5 and len(instrumented_packages) == 0:
            architectural_ghosts.append(
                "The codebase imports multiple instrumentable packages (e.g., "
                f"{', '.join(list(imported_packages)[:5])}) but has no Logfire instrumentation calls. "
                "This suggests observability coverage may be incomplete."
            )

        return {"issues": issues, "architectural_ghosts": architectural_ghosts}

    def check_integration(self, integration: str) -> bool:
        """Check if a specific integration is instrumented in the codebase."""
        for file_path in self.files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content, filename=str(file_path))
            except (SyntaxError, UnicodeDecodeError):
                continue

            visitor = InstrumentationVisitor()
            visitor.visit(tree)

            if integration in visitor.instrumented_calls:
                return True

        return False


class InstrumentationVisitor(ast.NodeVisitor):
    """AST visitor to detect Logfire instrumentation patterns."""

    def __init__(self):
        self.has_logfire_import = False
        self.imported_packages: Set[str] = set()
        self.instrumented_calls: Set[str] = set()

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.name.split(".")[0]
            if name == "logfire":
                self.has_logfire_import = True
            else:
                self.imported_packages.add(name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            name = node.module.split(".")[0]
            if name == "logfire":
                self.has_logfire_import = True
            else:
                self.imported_packages.add(name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Detect logfire.instrument_*() calls."""
        func = node.func

        if isinstance(func, ast.Attribute):
            if func.attr.startswith("instrument_"):
                # Check if it's logfire.instrument_*
                if isinstance(func.value, ast.Name) and func.value.id == "logfire":
                    instr_name = func.attr.replace("instrument_", "")
                    self.instrumented_calls.add(instr_name)

        self.generic_visit(node)
