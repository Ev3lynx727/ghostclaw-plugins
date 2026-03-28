"""Pattern analyzer — detects Logfire best practices and anti-patterns."""

import ast
import re
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple


class PatternAnalyzer:
    """Analyzes Logfire usage patterns for best practices and anti-patterns."""

    def __init__(self, root: str, files: List[str]):
        self.root = Path(root)
        self.files = [Path(f) for f in files]

    def analyze(self) -> Dict[str, Any]:
        """Run pattern analysis."""
        issues: List[Dict[str, Any]] = []
        architectural_ghosts: List[str] = []

        total_spans = 0
        spans_with_exceptions = 0
        files_with_logfire = 0
        log_calls_count = 0
        error_level_calls = 0

        for file_path in self.files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content, filename=str(file_path))
            except (SyntaxError, UnicodeDecodeError):
                continue

            file_issues, file_stats = self._analyze_file(tree, file_path, content)
            issues.extend(file_issues)

            if file_stats["has_logfire"]:
                files_with_logfire += 1
            total_spans += file_stats["span_count"]
            spans_with_exceptions += file_stats["spans_with_exception"]
            log_calls_count += file_stats["log_calls"]
            error_level_calls += file_stats["error_calls"]

        # Architectural analysis
        if total_spans > 0 and spans_with_exceptions == 0:
            architectural_ghosts.append(
                f"Found {total_spans} logfire.span() calls but none record exceptions. "
                "Add span.record_exception() or use try/except within spans for better error tracking."
            )

        if log_calls_count > 20 and error_level_calls == 0:
            architectural_ghosts.append(
                f"Found {log_calls_count} logfire log calls but no error-level logging. "
                "Consider using logfire.error() or logfire.exception() for error conditions."
            )

        return {"issues": issues, "architectural_ghosts": architectural_ghosts}

    def _analyze_file(
        self, tree: ast.AST, file_path: Path, content: str
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Analyze a single file for patterns."""
        issues: List[Dict[str, Any]] = []
        stats = {
            "has_logfire": False,
            "span_count": 0,
            "spans_with_exception": 0,
            "log_calls": 0,
            "error_calls": 0,
        }

        visitor = PatternVisitor(str(file_path))
        visitor.visit(tree)

        stats["has_logfire"] = visitor.has_logfire_import
        stats["span_count"] = visitor.span_count
        stats["spans_with_exception"] = visitor.spans_with_exception
        stats["log_calls"] = visitor.log_calls_count
        stats["error_calls"] = visitor.error_calls_count

        # Convert visitor findings to issues
        for finding in visitor.findings:
            issues.append(
                {
                    "rule_id": finding["rule_id"],
                    "title": finding["title"],
                    "message": finding["message"],
                    "severity": finding["severity"],
                    "file_path": str(file_path),
                    "line_start": finding["line"],
                    "line_end": finding["line"],
                    "metadata": finding.get("metadata", {}),
                }
            )

        return issues, stats


class PatternVisitor(ast.NodeVisitor):
    """AST visitor to detect Logfire usage patterns."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.has_logfire_import = False
        self.findings: List[Dict[str, Any]] = []

        # Stats
        self.span_count = 0
        self.spans_with_exception = 0
        self.log_calls_count = 0
        self.error_calls_count = 0

        # Track span context for exception handling analysis
        self._span_stack: List[ast.Call] = []

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
        """Detect Logfire calls and analyze patterns."""
        func = node.func

        if isinstance(func, ast.Attribute):
            # Check if it's a logfire method call
            if isinstance(func.value, ast.Name) and func.value.id == "logfire":
                method = func.attr

                # Count span calls
                if method == "span":
                    self.span_count += 1
                    self._span_stack.append(node)

                # Count log calls
                if method in ("trace", "debug", "info", "notice", "warning", "log"):
                    self.log_calls_count += 1

                # Count error calls
                if method in ("error", "fatal", "exception"):
                    self.error_calls_count += 1

                # Check for empty span messages
                if method == "span":
                    if node.args:
                        arg = node.args[0]
                        if isinstance(arg, ast.Constant):
                            if not arg.value or str(arg.value).strip() == "":
                                self.findings.append(
                                    {
                                        "rule_id": "LOGFIRE_EMPTY_SPAN_NAME",
                                        "title": "Empty span name",
                                        "message": "logfire.span() called with empty name. "
                                        "Use descriptive span names for better trace readability.",
                                        "severity": "low",
                                        "line": node.lineno,
                                        "metadata": {},
                                    }
                                )

                # Check for print() calls that could use logfire
                # (This is a heuristic - we look for print after logfire import)

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Check for try/except patterns in functions with spans."""
        has_span = False
        has_exception_handler = False

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    if (
                        isinstance(child.func.value, ast.Name)
                        and child.func.value.id == "logfire"
                    ):
                        if child.func.attr == "span":
                            has_span = True
            if isinstance(child, ast.ExceptHandler):
                has_exception_handler = True

        if has_span and has_exception_handler:
            self.spans_with_exception += 1

        self.generic_visit(node)

    def visit_With(self, node: ast.With):
        """Check for context manager span usage with exception handling."""
        # logfire.span() as context manager: with logfire.span("name"):
        for item in node.items:
            if isinstance(item.context_expr, ast.Call):
                func = item.context_expr.func
                if isinstance(func, ast.Attribute):
                    if isinstance(func.value, ast.Name) and func.value.id == "logfire":
                        if func.attr == "span":
                            self.span_count += 1
                            # Check if body has exception handling
                            for child in ast.walk(node):
                                if isinstance(child, ast.ExceptHandler):
                                    self.spans_with_exception += 1
                                    break

        self.generic_visit(node)
