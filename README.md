# Lloom

A config-driven, project-agnostic framework for training language models from scratch in pure PyTorch. One transformer implementation, one set of trainers, driven entirely by YAML — "a different model" means "a different config", not different code.

Lloom supplies the machinery: model zoo, data pipeline, tokenizer, trainers, finetuning, inference, eval, quantization, and pipeline automation. A *project* supplies the YAML configs, data, and thin CLI scripts that wire it to a specific corpus. Nothing in `lloom/` knows about any particular dataset.

Importing `lloom` pulls in no torch; the heavy subpackages (`lloom.model`, `lloom.train`, ...) are imported explicitly.

## Features

**Model** (`lloom.model`) — decoder-only transformer where every architecture choice is a `ModelConfig` field:

- Attention: MHA / GQA / MQA (`n_kv_heads`), optional QK-norm, sliding-window
- RoPE with linear / NTK scaling for context extension
- FFN: SwiGLU / GeGLU / GELU, or sparse MoE (top-k routing + Switch aux loss)
- RMSNorm / LayerNorm, tied or untied head, gradient checkpointing, KV-cache decode

**Data** (`lloom.data`) — uint16 `.npy` memmap token streams (many-GB corpus, few-MB RAM, free resume), curriculum-weighted multi-source sampling, and SFT example packing with prompt masking and block-diagonal attention.

**Tokenizer** (`lloom.tokenizer`) — SentencePiece train/load wrapper.

**Training** (`lloom.train`) — `Trainer` and `SFTTrainer`; optimizers AdamW / Muon / Lion (plus `MultiOptimizer`); cosine / WSD / linear / constant schedules; mixed objectives (causal + span corruption).

**Finetune** (`lloom.finetune`) — LoRA inject / merge / save-adapter.

**Inference** (`lloom.infer`) — KV-cache generation, checkpoint load and safetensors export, optional FastAPI/SSE server.

**Quantization** (`lloom.quant`) — dynamic int8.

**Eval** (`lloom.eval`) — perplexity, embeddings, retrieval (MRR/NDCG), clustering, and a unified `Evaluator`.

**Automation** (`lloom.config`, `lloom.pipeline`) — config merge `base < preset < --set` with a resolved snapshot per run, and a YAML pipeline runner to chain stages.

## Install

```bash
cd Lloom
pip install -e .               # core
pip install -e ".[serve]"      # + FastAPI inference server
pip install -e ".[train,dev]"  # + wandb logging, pytest
```

Blackwell GPUs (RTX 50-series) need a CUDA 12.8+ torch build:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128
```

## Quickstart

```python
import torch
from lloom.model import ModelConfig, TransformerLM

cfg = ModelConfig(vocab_size=32000, d_model=384, n_layers=6, n_heads=6)
model = TransformerLM(cfg)

ids = torch.randint(0, cfg.vocab_size, (2, 128))
logits, loss = model(ids, targets=ids)          # training step: CE (+ MoE aux) loss
out_ids = model.generate(ids[:, :8], max_new_tokens=32)
```

Change the architecture by changing the config — e.g. GQA + sparse MoE + sliding-window:

```python
cfg = ModelConfig(d_model=384, n_layers=6, n_heads=6, n_kv_heads=2,
                  n_experts=8, moe_top_k=2, sliding_window=256)
```

## Config system

Models are defined in YAML and merged in this order (later wins):

```
base config   <   preset   <   --set overrides
```

Presets are partial YAMLs (usually a `model:` block plus a few training tweaks) that layer over a base training config your project supplies. Overrides handle one-off tweaks without editing files. `save_snapshot` writes the fully resolved config beside each run for reproducibility.

```python
from lloom.config import load_config
cfg = load_config("config/training_config.yaml",   # your project's base config
                  preset="large",                   # bare name -> config/presets/large.yaml
                  sets=["training.optimizer=muon", "model.n_layers=24"])
```

## Presets

| Preset  | Params                    | Shape                      | Notes                                   |
|---------|---------------------------|----------------------------|-----------------------------------------|
| `nano`  | ~23M                      | d384/L6/H6                 | debug / fast pipeline shakedown         |
| `small` | ~40M                      | d512/L10/H8                | non-embedding params dominate           |
| `base`  | ~164M                     | d896/L14/H14               | dense default                           |
| `large` | ~454M                     | d1280/L24/H20, GQA kv4     | 16GB w/ grad-checkpoint + Muon          |
| `xl`    | ~1.06B                    | d2048/L22/H16, GQA kv4     | borderline 16GB; framework stress test  |
| `moe`   | ~73M total / ~30M active  | nano dims, 8 experts top-2 | sparse-scaling demo                     |

Presets are partial overlays: they set model dims (and a few training knobs) and merge over your base config.

## Package layout

```
lloom/
  config.py        config merge, dot-access, --set overrides, run snapshot
  model/           ModelConfig + transformer (attention, rope, layers, moe)
  data/            memmap token streams, mixture sampling, SFT packing
  tokenizer/       SentencePiece wrapper
  train/           Trainer, SFTTrainer, optimizers, schedules, objectives
  finetune/        LoRA
  infer/           generate (KV-cache), checkpoint I/O, FastAPI server
  quant/           dynamic int8
  eval/            perplexity, embed, retrieval, clustering, Evaluator
  pipeline.py      YAML stage runner
config/presets/    model-size presets (nano ... xl, moe)
tests/             test_lloom.py - every subsystem on synthetic data, CPU, < 1 min
```

## Tests

```bash
python tests/test_lloom.py     # or: pytest
```

Exercises every subsystem on synthetic data with no corpus or tokenizer training — CPU, under a minute.

## What's not included

Lloom is the framework, not a project. To train on real data you supply:

- a base training config (e.g. `config/training_config.yaml`) for presets to layer over, plus data / tokenizer / eval configs
- thin CLI scripts (`prepare_data.py`, `pretrain.py`, ...) that wire your corpus to lloom; the `lloom.pipeline` docstring shows the recipe format
