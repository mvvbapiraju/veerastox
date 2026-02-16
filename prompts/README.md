# Prompt Library

This directory stores reusable AI prompts for rebuilding, auditing, and extending this repository.

## Files

- `recreateme.md`: Canonical self-reconstruction prompt for this repository (source of truth).
- `recreate-project.md`: Generic full-fidelity template for other repos/projects.
- `recreate-project-lite.md`: Generic shorter template for quick regeneration tasks.

## Usage

1. Use `recreateme.md` when you need an exact Veerastox rebuild prompt.
2. Use the other templates only as scaffolds for new repos or variants.
3. Keep prompts in version control so changes are reviewed and traceable.

## Maintenance

- Update prompts when CLI contracts, outputs, or architecture changes.
- Treat `recreateme.md` as the first file to update whenever behavior changes.
- Reference exact files/paths and command names to reduce ambiguity.
- Do not include secrets in prompt files.
