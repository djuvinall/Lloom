# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Apache-2.0 `LICENSE` and `NOTICE`.
- GitHub Actions CI: ruff lint + pytest on Python 3.10–3.12 (CPU PyTorch).
- Packaging metadata in `pyproject.toml`: license, project URLs, classifiers.
- Community docs: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue/PR templates.
- `docs/ARCHITECTURE.md` design-rationale doc and a README pipeline diagram (Mermaid).
- `scripts/plot_loss.py` loss-curve plotter + `viz` extra; README Results section.
- README Status & roadmap section.

### Fixed
- Smoke test used `vocab_size: 300` (below SentencePiece's byte-fallback floor) and
  asserted a non-existent `val/perplexity/total` key; corrected to `512` and
  `perplexity/total`. Quoted `${run_name}` in the config-interpolation test's
  flow-mapping YAML so it parses.

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

[Unreleased]: https://github.com/djuvinall/Lloom/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/djuvinall/Lloom/releases/tag/v0.1.0
