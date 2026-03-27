#!/usr/bin/env python3
"""Quick benchmark runner for a single repo and condition."""

import json
import os
import subprocess
import sys


def run_condition(repo_path: str, condition: str):
    """Run ghostclaw analysis and return parsed JSON output."""
    if condition == "baseline":
        cmd = ["ghostclaw", "analyze", repo_path, "--no-ai", "--no-cache"]
    elif condition == "vector":
        cmd = ["ghostclaw", "analyze", repo_path, "--orchestrate", "--orchestrate-llm=false", "--no-ai", "--no-cache"]
    elif condition == "llm":
        cmd = ["ghostclaw", "analyze", repo_path, "--orchestrate", "--orchestrate-llm=true", "--no-ai", "--no-cache"]
    else:
        raise ValueError(f"Unknown condition: {condition}")

    print(f"Running: {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        return None
    try:
        data = json.loads(result.stdout)
        return data
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}", file=sys.stderr)
        return None

def extract_metrics(data: dict, condition: str) -> dict:
    meta = data.get("metadata", {})
    orch_meta = meta.get("orchestrator_metrics", {})
    plan = meta.get("orchestrator_plan", {})
    repo_profile = meta.get("repo_profile", {})

    # For baseline, orch_meta may be empty; dedupe stats might be elsewhere?
    # Baseline metadata may have plugins_run?
    plugins_selected = len(plan.get("plugins", [])) if condition != "baseline" else None
    plan_source = plan.get("metadata", {}).get("source", "N/A") if condition != "baseline" else "N/A"
    planning_ms = orch_meta.get("planning_duration_ms")
    execution_ms = orch_meta.get("execution_duration_ms")
    total_ms = orch_meta.get("total_duration_ms")
    cache_hit = orch_meta.get("cache_hit")
    qmd_hit = orch_meta.get("qmd_hit")
    concurrency = orch_meta.get("concurrency_used")
    dedup = orch_meta.get("deduplication", {})
    llm_usage = plan.get("metadata", {}).get("llm_usage", {})

    return {
        "condition": condition,
        "plugins_selected": plugins_selected,
        "plan_source": plan_source,
        "planning_ms": planning_ms,
        "execution_ms": execution_ms,
        "total_ms": total_ms,
        "cache_hit": cache_hit,
        "qmd_hit": qmd_hit,
        "concurrency_used": concurrency,
        "dedup_original": dedup.get("original_count"),
        "dedup_deduped": dedup.get("deduped_count"),
        "dedup_removed": dedup.get("duplicates_removed"),
        "total_lines": repo_profile.get("total_lines"),
        "languages": "|".join(f"{k}:{v}" for k, v in repo_profile.get("languages", {}).items()),
        "llm_total_tokens": llm_usage.get("total_tokens"),
    }

def main():
    if len(sys.argv) < 3:
        print("Usage: quick_benchmark.py <repo_path> <condition> [<output_csv>]")
        sys.exit(1)

    repo = sys.argv[1]
    condition = sys.argv[2]
    output_csv = sys.argv[3] if len(sys.argv) > 3 else None

    # Ensure clean state: remove .ghostclaw/storage in repo
    storage = os.path.join(repo, ".ghostclaw", "storage")
    if os.path.exists(storage):
        subprocess.run(["rm", "-rf", storage], check=True)

    data = run_condition(repo, condition)
    if not data:
        sys.exit(1)

    metrics = extract_metrics(data, condition)

    # Output as CSV
    fields = [
        "condition", "plugins_selected", "plan_source", "planning_ms", "execution_ms",
        "total_ms", "cache_hit", "qmd_hit", "concurrency_used",
        "dedup_original", "dedup_deduped", "dedup_removed",
        "total_lines", "languages", "llm_total_tokens"
    ]
    if output_csv:
        # If file doesn't exist, write header
        if not os.path.exists(output_csv):
            with open(output_csv, "w") as f:
                f.write(",".join(fields) + "\n")
        with open(output_csv, "a") as f:
            f.write(",".join(str(metrics.get(f, "")) for f in fields) + "\n")
        print(f"Wrote metrics to {output_csv}")
    else:
        print(",".join(fields))
        print(",".join(str(metrics.get(f, "")) for f in fields))

if __name__ == "__main__":
    main()
