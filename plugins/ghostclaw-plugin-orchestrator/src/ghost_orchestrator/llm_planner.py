"""LLM-based analysis planner using abstract LLM client."""

import json
import logging
from typing import Any, Optional

from .llm_client import LLMClient, create_llm_client
from .models import AnalysisPlan, OrchestratorConfig, RepositoryProfile

logger = logging.getLogger(__name__)


class LLMPlanner:
    """Uses an LLM to decide which plugins to run and in what order."""

    SYSTEM_PROMPT = (
        "You are an expert code quality engineer managing a static analysis pipeline.\n"
        "\n"
        "Given a repository profile and a list of available analysis plugins,\n"
        "your job is to:\n"
        "1. Select the most relevant plugins to run (at most {max_plugins})\n"
        "2. Order them logically (fast checks first, expensive ones later)\n"
        "3. Provide a brief rationale for each choice\n"
        "\n"
        "Consider:\n"
        "- Repository size and languages (avoid expensive analysis on tiny repos)\n"
        "- Likely issues based on frameworks used\n"
        "- Complementarity (don't duplicate effort)\n"
        "\n"
        "Output a JSON object with these exact keys:\n"
        "{\n"
        '  "plugins": ["plugin1", "plugin2", ...],\n'
        '  "rationale": {"plugin1": "reason", "plugin2": "reason"},\n'
        '  "confidence": 0.85,\n'
        '  "notes": "optional extra info"\n'
        "}\n"
        "\n"
        "Be concise. Only include plugins from the available list."
    )

    USER_PROMPT_TEMPLATE = """Repository:
{repo_summary}

Available plugins:
{plugin_descriptions}

Decide which plugins to run and in what order. Return JSON as specified."""

    def __init__(
        self,
        model_name: Optional[str],
        plugin_capabilities: dict[str, Any],
        config: OrchestratorConfig,
    ):
        self.model_name = model_name
        self.plugin_capabilities = plugin_capabilities
        self.config = config
        self.client: Optional[LLMClient] = None

    def _get_client(self) -> LLMClient:
        """Initialize or return cached LLM client."""
        if self.client is None:
            try:
                self.client = create_llm_client(self.model_name, {})
            except Exception as e:
                logger.error(f"Failed to create LLM client: {e}")
                raise
        return self.client

    async def plan(
        self,
        repo_profile: RepositoryProfile,
        available_plugins: list[str],
    ) -> AnalysisPlan:
        """
        Generate analysis plan using LLM.

        Returns an AnalysisPlan. If LLM fails, returns empty plan with low confidence.
        """
        if not self.model_name:
            raise ValueError("LLM model name not configured")

        try:
            client = self._get_client()

            # Build plugin descriptions
            descriptions = []
            for name in available_plugins:
                cap = self.plugin_capabilities.get(name)
                if cap:
                    cat_str = ', '.join(cap.categories)
                    desc = f"- {name}: {cap.description} (categories: {cat_str})"
                    if cap.languages:
                        lang_str = ', '.join(cap.languages)
                        desc += f" languages: {lang_str}"
                else:
                    desc = f"- {name}: (no description)"
                descriptions.append(desc)

            system_prompt = self.SYSTEM_PROMPT.format(
                max_plugins=self.config.max_plugins,
            )
            user_prompt = self.USER_PROMPT_TEMPLATE.format(
                repo_summary=repo_profile.summary(),
                plugin_descriptions="\n".join(descriptions),
            )

            logger.info(
                "Calling LLM %s for planning (plugins=%d)",
                self.model_name,
                len(available_plugins),
            )
            content, usage = await client.generate_plan(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1024,
                temperature=0.3,
            )

            # Parse JSON
            try:
                plan_dict = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(
                    "LLM returned invalid JSON: %s. Content: %s",
                    e,
                    content[:200],
                )
                return AnalysisPlan(
                    plugins=[],
                    rationale=[],
                    confidence=0.0,
                    metadata={"error": "invalid_json"},
                )

            # Validate structure
            if not isinstance(plan_dict.get("plugins"), list):
                raise ValueError("LLM response missing 'plugins' list")

            # Filter to only available plugins, preserve order, respect max_plugins
            max_plugins = self.config.max_plugins
            filtered = [p for p in plan_dict["plugins"] if p in available_plugins]
            selected = filtered[:max_plugins]
            rationales = [
                plan_dict.get("rationale", {}).get(p, "No rationale") for p in selected
            ]
            raw_confidence = plan_dict.get("confidence", 0.7)
            confidence = max(0.0, min(1.0, float(raw_confidence)))

            return AnalysisPlan(
                plugins=selected,
                rationale=rationales,
                confidence=confidence,
                metadata={
                    "source": "llm_planner",
                    "llm_model": self.model_name,
                    "llm_usage": usage,
                    "raw_response": content,
                    "notes": plan_dict.get("notes", ""),
                },
            )

        except Exception as e:
            logger.error(f"LLM planning failed: {e}")
            return AnalysisPlan(
                plugins=[],
                rationale=[],
                confidence=0.0,
                metadata={
                    "source": "llm_planner",
                    "error": str(e),
                },
            )

    async def close(self):
        """Close underlying client."""
        if self.client:
            await self.client.close()
