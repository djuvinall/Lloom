# Contributing to Lloom

Thanks for your interest in Lloom. Contributions of all sizes are welcome — bug
reports, docs fixes, new features, and presets.

## Ground rules

- `lloom/` is the framework and stays project-agnostic. Nothing in it should know
  about a specific corpus, dataset, or downstream project. Project-specific logic
  belongs in `textlm/` + `config/`.
- New architecture or training behavior should be a config field with one code
  path, not a fork of an existing one. "A different model" means "a different
  config", not different code.
- Keep `import lloom` torch-free. Heavy subpackages (`lloom.model`, `lloom.train`,
  ...) are imported explicitly.

## Development setup

```bash
git clone https://github.com/djuvinall/Lloom.git
cd Lloom

# CPU PyTorch is enough for the test suite:
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[serve,dev]"
```

## Before opening a PR

```bash
ruff check .        # lint (matches CI)
pytest              # framework units + CLI smoke test (CPU, no GPU needed)
```

CI runs the same lint + tests on Python 3.10–3.12. PRs need a green check.

- `tests/test_lloom.py` exercises every subsystem on synthetic tensors.
- `tests/test_scripts_smoke.py` runs the real CLI end to end on a tiny corpus
  with the `nano` preset. If you change stage wiring or path handoffs, run it.

Add or update tests for behavior you change. If you touch config merging,
run-namespacing, or model dims, cover it in the unit tests.

## Commit / PR style

- Keep commits focused; describe the "why", not just the "what".
- Reference any related issue in the PR description.
- Note any user-facing change in `CHANGELOG.md` under `Unreleased`.

## Reporting bugs

Open an issue using the bug template. Include the preset/config, the command you
ran, and the full traceback. A minimal repro on the `nano` preset is ideal.
