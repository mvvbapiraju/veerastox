# Recreate Project (Lite)

Use this prompt for a fast rebuild when you do not need exhaustive constraints.

---

Recreate this repository from scratch with working feature parity.

## Inputs

- Repo: `<REPO_NAME>`
- Language/runtime: `<RUNTIME>`
- Core file tree:

```text
<PASTE_TREE>
```

- Required commands:
  - `<CMD_1>`
  - `<CMD_2>`
  - `<CMD_3>`

- Critical env vars:
  - `<ENV_1>=<DEFAULT>`
  - `<ENV_2>=<DEFAULT>`

## Requirements

1. Rebuild packaging and dependencies.
2. Recreate CLI/web features with matching command interfaces.
3. Preserve default behavior and output files.
4. Keep paths/module names stable.
5. Do not skip key functionality.

## Validation

Run:

1. `<BUILD_OR_COMPILE_COMMAND>`
2. `<CLI_HELP_COMMAND>`
3. `<SMOKE_TEST_COMMAND>`

Confirm output artifacts:

- `<OUTPUT_FILE_1>`
- `<OUTPUT_FILE_2>`

## Output

Return all created file paths and full file contents.

---

Replace all placeholders before use.
