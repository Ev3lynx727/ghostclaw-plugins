#!/bin/bash
# Collect benchmark data for multiple repos and conditions.
# Prerequisites: repos listed in REPOS.txt, one path per line.
# Creates results.csv in current directory.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_CSV="${1:-results.csv}"

# Conditions to run (order matters for baseline first)
CONDITIONS=("baseline" "vector" "llm")

# Read repos
if [ $# -ge 2 ]; then
    REPOS_FILE="$2"
else
    REPOS_FILE="REPOS.txt"
fi

if [ ! -f "$REPOS_FILE" ]; then
    echo "Repos file not found: $REPOS_FILE" >&2
    echo "Create REPOS.txt with one repo path per line." >&2
    exit 1
fi

echo "condition,repo,plugins_selected,plugins_list,plan_source,planning_ms,execution_ms,total_ms,cache_hit,qmd_hit,concurrency_used,dedup_original,dedup_deduped,dedup_removed,total_lines,languages,llm_total_tokens" > "$OUTPUT_CSV"

while IFS= read -r repo || [ -n "$repo" ]; do
    # Skip empty lines and comments
    [[ -z "$repo" ]] && continue
    [[ "$repo" =~ ^# ]] && continue

    repo="$(echo "$repo" | xargs)"  # trim
    echo "Processing repo: $repo" >&2

    for cond in "${CONDITIONS[@]}"; do
        echo "  Condition: $cond" >&2
        # Run experiment; capture CSV line (skip header)
        line="$("$SCRIPT_DIR/run_experiment.sh" "$repo" "$cond" 2>/dev/null | tail -n +2)"
        if [ -n "$line" ]; then
            echo "$cond,$line" >> "$OUTPUT_CSV"
        else
            echo "  Warning: no output for $cond on $repo" >&2
        fi
    done
done < "$REPOS_FILE"

echo "Done. Results written to $OUTPUT_CSV"
