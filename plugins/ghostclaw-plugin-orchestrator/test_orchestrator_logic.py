#!/usr/bin/env python3
"""
Standalone test to validate orchestrator logic without going through CLI.
"""

import asyncio
import sys
from pathlib import Path

# Ensure we use the development version
sys.path.insert(0, str(Path(__file__).parent.parent / "ghostclaw-clone" / "src"))

from ghostclaw.core.analyzer import CodebaseAnalyzer
from ghostclaw.core.config import GhostclawConfig


async def main():
    repo_path = Path("/tmp/test_repo")
    print(f"Testing orchestrator in repo: {repo_path}")

    # Build config with orchestrator enabled
    config = GhostclawConfig(root=str(repo_path))
    config.orchestrator.enabled = True
    config.orchestrator.use_llm = False
    config.orchestrator.max_plugins = 5
    config.orchestrator.plan_only = True  # Don't execute plugins
    # Disable heavy adapters
    config.use_ai = False
    config.use_pyscn = False
    config.use_ai_codeindex = False

    analyzer = CodebaseAnalyzer(
        root=str(repo_path),
        config=config,
        progress_cb=lambda msg: print(f"Progress: {msg}"),
    )

    try:
        report = await analyzer.analyze()
        print("\n=== Analysis completed ===")
        metadata = report.get("metadata", {})
        print("Metadata keys:", list(metadata.keys()))

        if "orchestrator" in metadata:
            orch_data = metadata["orchestrator"]
            print("\n✅ Orchestrator was active!")
            print(f"Plan summary: {orch_data}")
        else:
            print("\n❌ Orchestrator metadata missing")

        # Print red flags if any
        red_flags = report.get("red_flags", [])
        if red_flags:
            print("\nRed flags:")
            for flag in red_flags:
                print(f" - {flag}")

    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
