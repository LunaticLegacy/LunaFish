# LunaFish — Superproject Index

LunaFish is the product superproject for **MiroFish**, an offline, traceable
stakeholder simulation for UTF-8 TXT/Markdown seed material. It runs on the
**llmfetcher** engine, which is vendored as a git submodule.

## Repository layout

| Path | Role |
| --- | --- |
| `mirofish/` | MiroFish product package; installed and imported as `llmfetcher.mirofish` (offline, deterministic mock provider — no API key or network required). |
| `llmfetcher/` | llmfetcher engine — git submodule pinned to `main`; provides the `llmfetcher` package and its subpackages. |
| `tests/` | Superproject tests: `test_mirofish_p0.py`. Engine tests live under `llmfetcher/tests/` and are run inside the submodule, not by the superproject CI. |
| `scripts/check_packaged_imports.py` | Imports every module of the installed `llmfetcher` wheel, including `llmfetcher.mirofish`. |
| `docs/semantic-map.md` | Source-tree → installed-package mapping and the CI wheel-verification flow. |
| `.github/workflows/ci.yml` | CI: matrix tests, compile checks, build + twine + fresh-venv wheel verification. |

## The llmfetcher submodule

The engine is pinned to the `main` branch (see `.gitmodules`). Initialize it
after cloning:

```bash
git clone https://github.com/LunaticLegacy/LunaFish.git
cd LunaFish
git submodule update --init --recursive
# or clone with submodules from the start:
# git clone --recurse-submodules https://github.com/LunaticLegacy/LunaFish.git
```

The canonical engine documentation is the submodule's own index:
[`./llmfetcher/INDEX.md`](llmfetcher/INDEX.md).

## Build / install / test

Requires Python 3.12 or later. Keep the submodule initialized first — the
superproject wheel bundles `./llmfetcher` as the `llmfetcher` package, so a
missing checkout breaks editable installs, tests, and builds alike.

```bash
python -m venv .venv && source .venv/bin/activate

# editable install; resolves llmfetcher.mirofish through the editable finder
python -m pip install -e .

# superproject tests (from the repo root)
python -m unittest discover -s tests -v

# build and verify the wheel
python -m pip install build twine
python -m build
twine check dist/*
python -m venv /tmp/llmfetcher-wheel-check
/tmp/llmfetcher-wheel-check/bin/python -m pip install dist/*.whl
/tmp/llmfetcher-wheel-check/bin/python scripts/check_packaged_imports.py
```

## MiroFish (product)

Offline, deterministic, fully traceable simulation: a world model with stable
IDs, evidence locations, entities/relations/roles, and explicit
`input_fact` vs `model_inference` provenance; sessions expose a
`queued → preparing → running → reporting → completed|failed|cancelled`
lifecycle. See `mirofish/` and `tests/test_mirofish_p0.py`; example usage is
in `README.md`.
