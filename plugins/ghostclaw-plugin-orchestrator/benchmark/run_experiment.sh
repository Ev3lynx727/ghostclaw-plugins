#!/bin/bash
# Run orchestrator benchmark for a given repo and condition.
# Usage: ./run_experiment.sh <repo_path> <condition> [<extra_ghostclaw_args>...]
#
# Conditions:
#   baseline    - run all plugins (no orchestrator)
#   vector      - orchestrator with use_llm=false
#   llm         - orchestrator with use_llm=true
#
# Examples:
#   ./run_experiment.sh /path/to/repo baseline --no-cache
#   ./run_experiment.sh /path/to/repo vector --orchestrate-llm=false
#
# Output: prints CSV line to stdout with metrics

set -e

if [ $# -lt 2 ]; then
    echo "Usage: $0 <repo_path> <condition> [extra ghostclaw args...]" >&2
    exit 1
fi

REPO="$1"
CONDITION="$2"
shift 2
EXTRA_ARGS="$@"

# Ensure clean state for baseline runs (orchestrator cache isn't used for baseline anyway)
# For orchestrator runs, we'll keep plan cache between runs for caching metric, but for fresh evaluation we want cache off initially.
# For simplicity, we'll not clear anything here; do it manually before full experiment.

# Build ghostclaw command
if [ "$CONDITION" = "baseline" ]; then
    # Run without orchestrator plugins; run all enabled plugins
    # Assume plugins are enabled via config; we just disable orchestrator
    CMD=(ghostclaw analyze "$REPO" --orchestrate=false "$EXTRA_ARGS")
elif [ "$CONDITION" = "vector" ]; then
    CMD=(ghostclaw analyze "$REPO" --orchestrate --orchestrate-llm=false "$EXTRA_ARGS")
elif [ "$CONDITION" = "llm" ]; then
    CMD=(ghostclaw analyze "$REPO" --orchestrate --orchestrate-llm=true "$EXTRA_ARGS")
else
    echo "Unknown condition: $CONDITION" >&2
    exit 1
fi

# Run analysis
echo "Running: ${CMD[@]}" >&2
"${CMD[@]}"

# Find the latest JSON report in the repo's .ghostclaw/storage/reports/
REPORT_DIR="$REPO/.ghostclaw/storage/reports"
LATEST_REPORT=$(ls -t "$REPORT_DIR"/*.json 2>/dev/null | head -1 || true)
if [ -z "$LATEST_REPORT" ]; then
    echo "No JSON report found in $REPORT_DIR" >&2
    exit 1
fi

# Extract metrics using Python script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/extract_metrics.py" "$LATEST_REPORT"
