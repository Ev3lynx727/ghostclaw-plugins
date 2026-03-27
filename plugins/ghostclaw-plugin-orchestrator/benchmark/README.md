# Benchmarking Tools

This directory contains tools for evaluating the orchestrator.

---

## extract_metrics.py

Extract key metrics from a Ghostclaw JSON report (orchestrator runs only).

**Usage:**

```bash
python3 extract_metrics.py /path/to/report.json > metrics.csv
```

Or combine multiple:

```bash
for f in reports/*.json; do
    python3 extract_metrics.py "$f"
done > all_metrics.csv
```

**Output CSV fields:**

- `report` — path to report file
- `plugins_selected` — number of plugins orchestrator chose
- `plan_source` — `vector_advisor` or `llm_planner`
- `planning_ms` — planning time (milliseconds)
- `execution_ms` — plugin execution time
- `total_ms` — total duration
- `cache_hit` — whether plan was loaded from cache (bool)
- `qmd_hit` — whether QMD vector similarity was used (bool)
- `concurrency_used` — max concurrent plugins setting
- `total_lines` — repo size (LOC)
- `languages` — pipe-separated `lang:count` pairs
- `llm_total_tokens` — total tokens if LLM planning

---

## run_experiment.sh

Wrapper to run a single experimental condition and extract metrics.

**Conditions:**
- `baseline` — all plugins, no orchestrator
- `vector` — orchestrator (use_llm=false)
- `llm` — orchestrator (use_llm=true)

**Usage:**

```bash
./run_experiment.sh /path/to/repo baseline --no-cache
./run_experiment.sh /path/to/repo vector --orchestrate-llm=false
./run_experiment.sh /path/to/repo llm --orchestrate-llm=true
```

Outputs a single CSV line to stdout with metrics.

**Note:** For repeatable experiments, clear `.ghostclaw/storage/` in the repo before each run to avoid caching effects (see `BENCHMARK.md`).

---

## Full Workflow

1. **Prepare repos** (clone, ensure clean `.ghostclaw/` storage state)
2. **Create `REPOS.txt`** with one absolute repo path per line
3. **Run data collection:**
   ```bash
   ./collect_results.sh results.csv
   ```
   This runs baseline, vector, and LLM conditions for each repo and appends to CSV.
4. **Analyze** with pandas, Excel, or R

Alternatively, run individual conditions with `./run_experiment.sh <repo> <condition>`.

See `BENCHMARK.md` for evaluation methodology and success criteria.
