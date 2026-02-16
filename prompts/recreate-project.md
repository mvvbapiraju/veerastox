# Recreate Project (Full Fidelity)

Use this prompt when you want an AI assistant to rebuild the entire repository with high accuracy.

---

You are a senior software engineer. Recreate this project from scratch with feature parity and matching behavior.

## Objective

Rebuild the repository end-to-end so commands, outputs, and user-facing behavior match the current implementation.

## Inputs

- Repository name: `<REPO_NAME>`
- Primary language/runtime: `<LANGUAGE_AND_RUNTIME>`
- Package manager/build system: `<BUILD_SYSTEM>`
- Project root structure:

```text
<PASTE_FILE_TREE_HERE>
```

- Key docs/specs:
  - `<DOC_1_PATH>`
  - `<DOC_2_PATH>`
  - `<DOC_3_PATH>`

## Hard Requirements

1. Recreate all directories and files needed for a working project.
2. Preserve CLI command names, flags, defaults, and output messages.
3. Preserve data schemas (CSV/JSON/DB), field names, and column order.
4. Preserve environment variable names and fallback behavior.
5. Preserve all user-facing web/API behavior and route contracts.
6. Preserve package metadata, entrypoints, and dependency constraints.
7. Preserve known quirks required for compatibility.
8. Do not silently omit functionality.

## Repository Contracts To Preserve

### 1) Setup and Build

- Install commands:
  - `<INSTALL_COMMAND_1>`
  - `<INSTALL_COMMAND_2>`
- Build/compile commands:
  - `<BUILD_COMMAND_1>`
  - `<BUILD_COMMAND_2>`

### 2) Runtime Commands

- Command: `<CMD_1>`
  - Flags: `<FLAGS_AND_DEFAULTS>`
  - Behavior: `<EXPECTED_BEHAVIOR>`
  - Outputs: `<FILES/LOGS>`
- Command: `<CMD_2>`
  - Flags: `<FLAGS_AND_DEFAULTS>`
  - Behavior: `<EXPECTED_BEHAVIOR>`
  - Outputs: `<FILES/LOGS>`

### 3) Data Pipeline

- Data sources: `<SOURCE_APIS_OR_FILES>`
- Fetch interval/range defaults: `<DEFAULTS>`
- Transform logic:
  - `<TRANSFORM_1>`
  - `<TRANSFORM_2>`
- Output paths:
  - `<OUTPUT_PATH_1>`
  - `<OUTPUT_PATH_2>`

### 4) App/UI Requirements

- Framework: `<WEB_FRAMEWORK>`
- Pages/tabs/routes:
  - `<PAGE_1>`
  - `<PAGE_2>`
- Core UI components:
  - `<TABLES>`
  - `<CHARTS>`
  - `<METRICS>`
- Caching and refresh behavior:
  - `<CACHE_TTL_RULES>`
  - `<AUTO_REFRESH_RULES>`

### 5) Config and Environment

- Required env vars:
  - `<ENV_VAR_1>=<DEFAULT>`
  - `<ENV_VAR_2>=<DEFAULT>`
- Config files:
  - `<CONFIG_FILE_1>`
  - `<CONFIG_FILE_2>`

### 6) Packaging

- Package name/version: `<NAME>/<VERSION>`
- Python version or runtime constraint: `<RUNTIME_CONSTRAINT>`
- Console entrypoints:
  - `<ENTRYPOINT_1>`
  - `<ENTRYPOINT_2>`

## Edge Cases and Compatibility Notes

- `<EDGE_CASE_1>`
- `<EDGE_CASE_2>`
- `<KNOWN_QUIRK_1>`

## Quality Bar

1. Add type hints and keep function boundaries clean.
2. Keep behavior-compatible logging/print strings.
3. Avoid unnecessary refactors that change external behavior.
4. Keep file paths and module names stable.

## Validation Checklist

Run and pass:

1. `python3 -m compileall <SRC_DIRS>`
2. `<HELP_COMMAND_1>`
3. `<HELP_COMMAND_2>`
4. `<PIPELINE_SMOKE_TEST>`
5. `<CLEANUP_TEST>`

Expected artifacts after smoke test:

- `<ARTIFACT_1>`
- `<ARTIFACT_2>`
- `<ARTIFACT_3>`

## Output Format

1. Print each created file path.
2. Print full file contents for each file.
3. Include exact commands used for validation.
4. End with a short “parity checklist” confirming preserved features.

---

Fill every placeholder (`<...>`) before use.
