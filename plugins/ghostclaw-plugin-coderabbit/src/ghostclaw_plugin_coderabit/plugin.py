"""
Ghostclaw Adapter: coderabbit
"""
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from ghostclaw.core.adapters.base import MetricAdapter, AdapterMetadata
from ghostclaw.core.adapters.hooks import hookimpl


class CustomAdapter(MetricAdapter):
    """CodeRabbit AI code review integration."""

    def get_metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            name="coderabbit",
            version="0.1.0",
            description="Integrates CodeRabbit CLI for AI-powered code reviews",
            dependencies=["coderabbit>=0.3.0"]
        )

    async def is_available(self) -> bool:
        """Check if coderabbit CLI is installed and accessible."""
        try:
            result = subprocess.run(
                ["coderabbit", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    async def analyze(self, root: str, files: List[str]) -> Dict[str, Any]:
        """
        Run coderabbit review on the repository.

        Args:
            root: Repository root path
            files: List of file paths (unused; coderabbit reviews the whole repo)

        Returns:
            Dict with 'issues', 'architectural_ghosts', 'red_flags' keys.
        """
        return await self.ghost_analyze(root, files)

    def _detect_base_branch(self, root: str) -> Optional[str]:
        """Detect a suitable base branch for coderabbit review.

        Prefers a branch that is an ancestor of the current HEAD to avoid
        'no merge base' errors. Tries common branch names in order.
        """
        import subprocess

        # Preferred order: main, master (most common)
        for branch in ["main", "master"]:
            try:
                # Check if branch exists and has a merge base with HEAD
                subprocess.run(
                    ["git", "merge-base", "--is-ancestor", branch, "HEAD"],
                    cwd=root,
                    capture_output=True,
                    timeout=5,
                    check=True
                )
                return branch
            except subprocess.CalledProcessError:
                # Not an ancestor or doesn't exist
                continue

        # Fallback: try any local branch tracking remote default
        try:
            result = subprocess.run(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                ref = result.stdout.strip()
                if ref:
                    branch = ref.split('/')[-1]
                    # Verify it's an ancestor
                    try:
                        subprocess.run(
                            ["git", "merge-base", "--is-ancestor", branch, "HEAD"],
                            cwd=root,
                            capture_output=True,
                            timeout=5,
                            check=True
                        )
                        return branch
                    except subprocess.CalledProcessError:
                        pass
        except Exception:
            pass

        return None

    @hookimpl
    async def ghost_analyze(self, root: str, files: List[str]) -> Dict[str, Any]:
        issues = []
        architectural_ghosts = []
        red_flags = []

        # Check for API key
        api_key = os.environ.get("CODERABBIT_API_KEY")
        if not api_key:
            red_flags.append("CODERABBIT_MISSING_API_KEY: CodeRabbit API key not configured (set CODERABBIT_API_KEY environment variable)")
            return {
                "issues": issues,
                "architectural_ghosts": architectural_ghosts,
                "red_flags": red_flags
            }

        # Build command: use --type all and auto-detect base branch
        cmd = ["coderabbit", "review", "--plain", "--no-color", "--type", "all", "--cwd", root]

        # Detect and add base branch if available
        base_branch = self._detect_base_branch(root)
        if base_branch:
            cmd.extend(["--base", base_branch])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            output = result.stdout or result.stderr

            # Always try to parse output, even if returncode != 0
            if output:
                parsed_issues = self._parse_coderabbit_output(output, root)
                issues.extend(parsed_issues)

            # If coderabbit returned non-zero, add a red flag but keep any parsed issues
            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                red_flags.append(f"CODERABBIT_ERROR: CodeRabbit exited with code {result.returncode}: {error_msg[:300]}")
                return {
                    "issues": issues,
                    "architectural_ghosts": architectural_ghosts,
                    "red_flags": red_flags
                }

        except subprocess.TimeoutExpired:
            red_flags.append("CODERABBIT_TIMEOUT: CodeRabbit review timed out (exceeded 5 minutes)")
        except Exception as e:
            red_flags.append(f"CODERABBIT_EXCEPTION: Unexpected error running CodeRabbit: {str(e)[:200]}")

        return {
            "issues": issues,
            "architectural_ghosts": architectural_ghosts,
            "red_flags": red_flags
        }

    def _parse_coderabbit_output(self, output: str, repo_root: str) -> List[Dict[str, Any]]:
        """
        Parse coderabbit plain text output into list of issue dicts.

        Expected format (based on actual output):
        ============================================================================
        File: <path>
        Line: <start> to <end>  (or 'Line: <num>' single line)
        Type: <issue_type>      (e.g., potential_issue, bug, security, etc.)
        Comment:
        <description>

        [possible "Prompt for AI Agent:" section]
        ============================================================================
        """
        issues = []
        current_issue = None
        in_comment = False

        for line in output.splitlines():
            line = line.rstrip()

            # Detect section separator (===) - signals start of new finding or end
            if line.startswith("==="):
                if current_issue:
                    issues.append(current_issue)
                    current_issue = None
                in_comment = False
                continue

            # Detect File line
            if line.startswith("File:"):
                file_path = line.replace("File:", "").strip()
                if current_issue:
                    issues.append(current_issue)
                current_issue = {
                    "rule_id": "CODERABBIT_REVIEW",
                    "title": "",  # will get from next lines
                    "message": "",
                    "severity": "medium",  # default; adjust based on Type if needed
                    "file_path": str(Path(repo_root) / file_path) if file_path else repo_root,
                    "line_start": 0,
                    "line_end": 0,
                    "metadata": {"source": "coderabbit"}
                }
                in_comment = False
                continue

            # Detect Line line
            if line.startswith("Line:") and current_issue:
                line_part = line.replace("Line:", "").strip()
                # Can be "36 to 37" or "123" or "123 to 125"
                try:
                    if " to " in line_part:
                        start, end = line_part.split(" to ")
                        current_issue["line_start"] = int(start.strip())
                        current_issue["line_end"] = int(end.strip())
                    else:
                        num = int(line_part.split()[0])
                        current_issue["line_start"] = num
                        current_issue["line_end"] = num
                except (ValueError, IndexError):
                    pass
                continue

            # Detect Type line (maps to severity)
            if line.startswith("Type:") and current_issue:
                type_val = line.replace("Type:", "").strip().lower()
                # Map CodeRabbit types to severity levels
                severity_map = {
                    "security": "high",
                    "bug": "medium",
                    "potential_issue": "low",
                    "style": "low",
                    "performance": "medium",
                    "maintainability": "low",
                    "error": "high",
                    "warning": "medium",
                    "info": "info"
                }
                current_issue["severity"] = severity_map.get(type_val, "medium")
                continue

            # Detect Comment: line - starts the description block
            if line.startswith("Comment:") and current_issue:
                in_comment = True
                # First line of comment after colon
                comment_text = line.replace("Comment:", "", 1).strip()
                if comment_text:
                    current_issue["message"] = comment_text
                continue

            # Continue capturing comment lines
            if in_comment and current_issue and line.strip():
                if current_issue["message"]:
                    current_issue["message"] += "\n" + line.strip()
                else:
                    current_issue["message"] = line.strip()

            # Capture title from first non-blank line after File/Line/Type if title empty
            if current_issue and not current_issue["title"] and line.strip() and not line.startswith(("File:", "Line:", "Type:", "Comment:", "===", "Prompt for")):
                current_issue["title"] = line.strip()

        # Append last issue if exists
        if current_issue:
            issues.append(current_issue)

        return issues

    @hookimpl
    def ghost_get_metadata(self) -> Dict[str, Any]:
        """Hook implementation — returns plugin metadata for listing."""
        meta = self.get_metadata()
        return {
            "name": meta.name,
            "version": meta.version,
            "description": meta.description,
            "available": True
        }
