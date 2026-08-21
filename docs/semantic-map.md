# Semantic map

This document maps the LunaFish superproject's source tree to the installed
Python distribution and explains how CI proves the built wheel is complete and
self-consistent.

## Packaging relationship

LunaFish is a superproject. The `llmfetcher` engine is vendored as a git
submodule at [`../llmfetcher/`](../llmfetcher/) (pinned to `main`), and the
MiroFish product lives at [`../mirofish/`](../mirofish/). A single wheel is
built from the superproject root and installs one distribution named
`llmfetcher`:

| Source path | Installed import package |
| --- | --- |
| `./llmfetcher/` (submodule) | `llmfetcher` root package plus subpackages: `context_handlers`, `fetcher_handlers`, `graph_memory`, `memory`, `rag_module` (incl. `rag_module.knowledge`), `rag_module_tlb`, `swarm_module`, `tools` |
| `./mirofish/` | `llmfetcher.mirofish` |

The superproject `pyproject.toml` declares this under `[tool.setuptools]`:
`package-dir` maps the `llmfetcher` root package into the submodule checkout
(`./llmfetcher`) and `llmfetcher.mirofish` to `./mirofish`, while the explicit
`packages` list enumerates every shipped subpackage. Static assets under the
submodule's `web/` are shipped via `[tool.setuptools.package-data]`.

The wheel — not the working tree — is what users install, so a missing or
stale submodule checkout breaks editable installs and wheel builds alike.
CI therefore always initializes submodules before installing, testing, or
building.

## `scripts/check_packaged_imports`

| Symbol | Responsibility | Calls / called by |
| --- | --- | --- |
| `packaged_modules` | Imports the installed root package (`llmfetcher`) and recursively discovers every package module with `pkgutil.walk_packages` — this now includes `llmfetcher.mirofish`. | Called by `main`. |
| `import_modules` | Imports all discovered modules while collecting every failure instead of stopping at the first exception. | Called by `main`. |
| `main` | Prints one status line per module and exits non-zero when any import fails. | Script entry point; invoked by `.github/workflows/ci.yml`. |

## CI verification flow

The build job verifies the installed wheel, not the source checkout:

1. `python -m build` at the superproject root produces `dist/*.whl` (the
   submodule checkout is present because CI initializes it with
   `actions/checkout@v4` + `submodules: recursive`).
2. A fresh virtual environment installs the wheel
   (`pip install dist/*.whl`).
3. `scripts/check_packaged_imports.py` runs inside that venv: it imports the
   installed `llmfetcher` package and every module `pkgutil` discovers under
   it — including `llmfetcher.mirofish` — so a wheel that omitted or misplaced
   MiroFish (or any engine subpackage) fails CI.
