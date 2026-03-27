#!/usr/bin/env python3
"""Extract orchestrator metrics from a Ghostclaw JSON report."""

import json
import sys
from pathlib import Path


def extract_metrics(report_path: Path) -> dict:
    """Parse a Ghostclaw JSON report and return orchestrator metrics."""
    data = json.loads(report_path.read_text())
    meta = data.get("metadata", {})
    orch_meta = meta.get("orchestrator_metrics", {})
    plan = meta.get("orchestrator_plan", {})

    result = {
        "report": str(report_path),
        "plugins_selected": len(plan.get("plugins", [])),
        "plugins_list": plan.get("plugins", []),
        "plan_source": plan.get("metadata", {}).get("source", "unknown"),
        "planning_ms": orch_meta.get("planning_duration_ms"),
        "execution_ms": orch_meta.get("execution_duration_ms"),
        "total_ms": orch_meta.get("total_duration_ms"),
        "cache_hit": orch_meta.get("cache_hit", False),
        "qmd_hit": orch_meta.get("qmd_hit", False),
        "concurrency_used": orch_meta.get("concurrency_used"),
        "deduplication": orch_meta.get("deduplication", {}),
        "llm_usage": plan.get("metadata", {}).get("llm_usage", {}),
        "repo_profile": meta.get("repo_profile", {}),
    }
    return result

def main():
    if len(sys.argv) < 2:
        print("Usage: extract_metrics.py <report.json> [<report2.json> ...]")
        sys.exit(1)

    reports = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.exists():
            reports.append(extract_metrics(p))
        else:
            print(f"Warning: {arg} not found", file=sys.stderr)

    # Output as CSV to stdout
    if not reports:
        return

    # Determine CSV fields
    fields = [
        "report", "plugins_selected", "plan_source", "planning_ms", "execution_ms",
        "total_ms", "cache_hit", "qmd_hit", "concurrency_used",
        "total_lines", "languages", "llm_total_tokens"
    ]
    print(",".join(fields))

    for r in reports:
        lang_str = "|".join(f"{k}:{v}" for k, v in r["repo_profile"].get("languages", {}).items())
        llm_usage = r["llm_usage"]
        llm_tokens = llm_usage.get("total_tokens", "")
        row = [
            r["report"],
            r["plugins_selected"],
            r["plan_source"],
            r.get("planning_ms", ""),
            r.get("execution_ms", ""),
            r.get("total_ms", ""),
            r.get("cache_hit", ""),
            r.get("qmd_hit", ""),
            r.get("concurrency_used", ""),
            r["repo_profile"].get("total_lines", ""),
            lang_str,
            llm_tokens,
        ]
        print(",".join(str(v) for v in row))

if __name__ == "__main__":
    main()
