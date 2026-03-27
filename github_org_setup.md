# Setting Up the Ghostclaw Community Organization

As requested, here is the recommended specification for organizing community plugins on GitHub.

## Organization Structure

We recommend creating a dedicated GitHub Organization (e.g., `ghostclaw-community` or `ghostclaw-plugins`) rather than cluttering the core repository.

### Monorepo vs Polyrepo
Given the lightweight nature of Ghostclaw plugins and the standard `pip install` entry-point mechanism, a **Monorepo** is the recommended approach for community plugins.

**Structure:**
```text
ghostclaw-community/
├── .github/workflows/          # Central CI/CD (PyPI publishing, linting)
├── plugins/
│   ├── ghostclaw-plugin-bandit/
│   ├── ghostclaw-plugin-coderabbit/
│   └── ghostclaw-plugin-semgrep/
├── templates/
│   └── plugin-template/        # The scaffold starter
├── CONTRIBUTING.md             # Your generated contributor guide
└── PLUGIN_API.md               # The API documentation
```

### CI/CD Requirements
You should set up a GitHub Action that:
1. Triggers on changes to paths `plugins/*`.
2. Identifies the modified plugin directory.
3. Automatically increments the version or reads the new `pyproject.toml` version tag.
4. Uses `twine` to publish directly to PyPI under the `ghostclaw-plugin-*` prefix.

### Next Steps (Manual)
1. Go to GitHub and create the new organization.
2. Initialize the repo with the contents of this `ghostclaw-plugins` workspace.
3. Add a link to the community plugins repository in the **main `ghostclaw` core documentation**.
