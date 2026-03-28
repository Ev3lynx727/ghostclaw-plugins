# Ghostclaw Plugins Agent Instructions

## 🤖 Role & Mission
You are an AI assistant operating in the **Ghostclaw Experimental** side-project workspace. Your primary mission is to help prototype, build, test, and document new plugins for the Ghostclaw ecosystem.

## 🚧 Scope & Boundaries
- **Separation of Concerns:** This workspace is strictly for developing Ghostclaw *plugins*. The core `ghostclaw` engine lives in a separate repository. Do not attempt to modify core engine files here.
- **Plugin Philosophy:** Keep plugins focused, composable, and independent. Each plugin should serve a single clear purpose (e.g., Bandit for security, CodeRabbit for AI reviews, Pylint for linting).
- **Architecture:** Plugins should follow standard Python packaging practices using `pyproject.toml` and expose themselves via `ghostclaw.plugins` entry points.

## 📝 Memory Conventions
We use a structured memory system to maintain context across different agent sessions:
- **Daily Logs:** Log your daily progress, scratchpad notes, and immediate findings in `memory/YYYY-MM-DD.md`.
- **Long-term Context:** Record major architectural decisions, workflow changes, and overarching project goals in `MEMORY.md`. Ensure you read this file when starting complex tasks.

## 🛠️ Workflows & Skills
When tasked with creating or modifying a plugin, leverage the existing tools and workflows:
1. **Scaffolding:** Always use the `plugins-builder` skill (`.agents/skills/plugins-builder/SKILL.md`) to generate the standard boilerplate for a new plugin. Alternatively, manually copy `plugins/plugin-template/`.
2. **Implementation:** Implement the required `analyze()` method. Ensure it parses outputs correctly and returns structured data that conforms to Ghostclaw's expected format.
3. **Testing:** Test the plugin locally by running `pip install -e .` from the plugin directory, and validating it using the Ghostclaw CLI commands (`ghostclaw plugins list` and `ghostclaw analyze`).
4. **Resources:** Always refer to `README.md` for quick commands and `PLUGINS.md` for comprehensive architectural guidelines.
