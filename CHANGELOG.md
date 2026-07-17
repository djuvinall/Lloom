# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-07-17

### Changed
- All wandb code now lives in `lloom/wandb_logging.py`, gated by the
  `WANDB_ENABLED` environment variable: unset/falsy means fully inert (no
  import, no network, no `wandb.init()`); CSV logging remains always-on with
  no flag. `--wandb` on the training scripts now sets `WANDB_ENABLED=1` for
  the process, and the dead `logging.wandb.enabled` config key was removed
  (`logging.wandb.project` still configures the project name). `wandb` is no
  longer installed by `requirements.txt`; use `.[train]`.

### Fixed
- `tests/test_scripts_smoke.py` excluded any directory named `data` from its
  repo copy — including the `lloom/data` subpackage — so the pretrain stage
  failed with `ModuleNotFoundError`. The exclusion now applies only to the
  top-level corpus `data/`. The smoke pipeline now also covers
  `finetune_sft_lora.py`.
- Trainers guarantee a `best.pt` when training ends before the first
  `eval_interval` (final validation), so `finetune_sft_lora.py` no longer
  crashes on tiny datasets like the bundled `data/sft/sample.jsonl`.
- `train_tokenizer` clamps `vocab_size` (with a warning) to SentencePiece's
  reported maximum instead of failing, so the out-of-box pretrain pipeline
  runs on the bundled sample corpus without config edits.
- The serve web UI's Q&A mode now templates with the `<|prompt|>`/`<|response|>`
  tokens the bundled SFT setup actually trains with (was nonexistent
  `<|question|>`/`<|answer|>`).
- Preflight errors when the objectives mix includes span corruption but the
  tokenizer lacks a `<|mask|>` token (previously an embedding IndexError deep
  into training).
- `checkpoint.save_interval` is honored for `last.pt` + rolling `step_*.pt`
  saves (was dead config; saving rode on `evaluation.eval_interval`).
- `serve.py` default checkpoint path updated to the `runs/<run_name>/` layout.
- Clear constructor error for token streams too short to form one training
  window; friendlier error for a missing preset file path; the evaluator no
  longer feeds `retrieval_pairs.jsonl` / `themed.jsonl` rows into QA
  generation.
- Smoke test used `vocab_size: 300` (below SentencePiece's byte-fallback floor) and
  asserted a non-existent `val/perplexity/total` key; corrected to `512` and
  `perplexity/total`. Quoted `${run_name}` in the config-interpolation test's
  flow-mapping YAML so it parses.

### Removed
- Unused `tqdm` dependency (was never imported).

### Added
- Python 3.13 in the CI test matrix and package classifiers.
- Apache-2.0 `LICENSE` and `NOTICE`.
- GitHub Actions CI: ruff lint + pytest on Python 3.10–3.13 (CPU PyTorch),
  on current `actions/checkout` / `actions/setup-python` (Node 24).
- Packaging metadata in `pyproject.toml`: license, project URLs, classifiers.
- Community docs: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue/PR templates.
- `docs/ARCHITECTURE.md` design-rationale doc and a README pipeline diagram (Mermaid).
- `scripts/plot_loss.py` loss-curve plotter + `viz` extra; README Results section.
- README Status & roadmap section.

## [0.1.0] - 2026-06-19

### Added
- Initial standalone release of the `lloom` framework, extracted from HolyLLM.
- Model zoo (MHA/GQA/MQA, RoPE scaling, SwiGLU/GeGLU/GELU, MoE, QK-norm,
  sliding-window, gradient checkpointing, KV-cache decode).
- Data pipeline (uint16 `.npy` memmap streams, curriculum-weighted sampling,
  SFT packing with prompt masking and block-diagonal attention).
- SentencePiece tokenizer wrapper.
- `Trainer` / `SFTTrainer`; AdamW / Muon / Lion optimizers; cosine / WSD /
  linear / constant schedules; mixed causal + span-corruption objectives.
- LoRA finetune (inject / merge / save-adapter).
- Inference: KV-cache generation, checkpoint + safetensors export, optional
  FastAPI/SSE server.
- Dynamic int8 quantization.
- Eval suite: perplexity, embeddings, retrieval (MRR/NDCG), clustering.
- Config system (`base < preset < --set`) with per-run snapshot and
  `${run_name}` artifact namespacing; YAML pipeline runner.
- `textlm` reference project + Stage 0–5 CLI scripts and preflight validation.
- Presets: nano, small, base, large, xl, moe.

[Unreleased]: https://github.com/djuvinall/Lloom/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/djuvinall/Lloom/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/djuvinall/Lloom/releases/tag/v0.1.0
