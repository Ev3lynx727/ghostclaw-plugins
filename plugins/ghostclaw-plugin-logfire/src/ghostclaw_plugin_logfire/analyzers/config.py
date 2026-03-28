"""Configuration analyzer — checks for proper Logfire setup."""

import ast
import os
from pathlib import Path
from typing import Dict, List, Any, Set


class ConfigAnalyzer:
    """Analyzes Logfire configuration patterns in Python files."""

    # Files that typically contain app configuration
    CONFIG_FILES = {"settings.py", "config.py", "main.py", "app.py", "__init__.py"}

    def __init__(self, root: str, files: List[str]):
        self.root = Path(root)
        self.files = [Path(f) for f in files]

    def analyze(self) -> Dict[str, Any]:
        """Run all configuration checks."""
        issues: List[Dict[str, Any]] = []
        red_flags: List[str] = []

        has_logfire_import = False
        has_configure_call = False
        has_send_to_logfire_false = False
        configure_files: List[Path] = []

        for file_path in self.files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content, filename=str(file_path))
            except (SyntaxError, UnicodeDecodeError):
                continue

            visitor = LogfireConfigVisitor()
            visitor.visit(tree)

            if visitor.has_logfire_import:
                has_logfire_import = True

            if visitor.has_configure_call:
                has_configure_call = True
                configure_files.append(file_path)

            if visitor.has_send_to_logfire_false:
                has_send_to_logfire_false = True

            # Check for hardcoded tokens (security issue)
            if visitor.hardcoded_tokens:
                for token_info in visitor.hardcoded_tokens:
                    red_flags.append(
                        f"Potential hardcoded Logfire token/API key in {file_path}:"
                        f"{token_info['line']} — rotate this credential immediately"
                    )

        # If logfire is imported but never configured
        if has_logfire_import and not has_configure_call:
            issues.append(
                {
                    "rule_id": "LOGFIRE_NOT_CONFIGURED",
                    "title": "Logfire imported but not configured",
                    "message": "logfire is imported but logfire.configure() was never called. "
                    "Observability data will not be collected.",
                    "severity": "high",
                    "file_path": str(self.root),
                    "line_start": 0,
                    "line_end": 0,
                    "metadata": {"configure_files": []},
                }
            )

        # If using local mode (send_to_logfire=False) — informational
        if has_send_to_logfire_false:
            issues.append(
                {
                    "rule_id": "LOGFIRE_LOCAL_MODE",
                    "title": "Logfire running in local-only mode",
                    "message": "Logfire is configured with send_to_logfire=False. "
                    "Data will not be sent to the Logfire cloud.",
                    "severity": "info",
                    "file_path": str(configure_files[0])
                    if configure_files
                    else str(self.root),
                    "line_start": 0,
                    "line_end": 0,
                    "metadata": {},
                }
            )

        return {"issues": issues, "red_flags": red_flags}


class LogfireConfigVisitor(ast.NodeVisitor):
    """AST visitor to detect Logfire configuration patterns."""

    def __init__(self):
        self.has_logfire_import = False
        self.has_configure_call = False
        self.has_send_to_logfire_false = False
        self.hardcoded_tokens: List[Dict[str, Any]] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name == "logfire" or alias.name.startswith("logfire."):
                self.has_logfire_import = True
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module and (
            node.module == "logfire" or node.module.startswith("logfire.")
        ):
            self.has_logfire_import = True
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Check for logfire.configure() calls
        func = node.func

        # Direct: logfire.configure()
        if isinstance(func, ast.Attribute):
            if func.attr == "configure":
                # Check if it's logfire.configure
                if isinstance(func.value, ast.Name) and func.value.id == "logfire":
                    self.has_configure_call = True
                    self._check_configure_args(node)

        self.generic_visit(node)

    def _check_configure_args(self, node: ast.Call):
        """Check configure() arguments for send_to_logfire=False."""
        for keyword in node.keywords:
            if keyword.arg == "send_to_logfire":
                # Check if it's False
                if (
                    isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is False
                ):
                    self.has_send_to_logfire_false = True

    def visit_Assign(self, node: ast.Assign):
        """Check for hardcoded tokens in environment variable assignments."""
        # Look for patterns like: os.environ["LOGFIRE_TOKEN"] = "lgf_..."
        for target in node.targets:
            if isinstance(target, ast.Subscript):
                if isinstance(target.value, ast.Attribute):
                    if target.value.attr in ("environ", "environb"):
                        if isinstance(target.slice, ast.Constant):
                            key = target.slice.value
                            if key in ("LOGFIRE_TOKEN", "LOGFIRE_API_KEY"):
                                if isinstance(node.value, ast.Constant):
                                    val = node.value.value
                                    if isinstance(val, str) and len(val) > 10:
                                        self.hardcoded_tokens.append(
                                            {"line": node.lineno, "key": key}
                                        )
        self.generic_visit(node)
