"""Pre-flight validation: fail fast on data/config problems before a run burns
GPU time. Each check returns (errors, warnings); errors should stop a pipeline,
warnings are printed but non-fatal. Kept dependency-light (numpy/sentencepiece
imported lazily) so it can run as a cheap gate stage.
"""
from __future__ import annotations

import json
from pathlib import Path


def _stream_len(path: Path) -> int:
    import numpy as np
    return int(np.load(path, mmap_mode="r").shape[0])


def check_pretrain(cfg, data_cfg, sources) -> tuple[list[str], list[str]]:
    """Validate the inputs Stage 1 depends on: tokenizer, token streams, and
    that each stream is long enough to form a window at the configured seq_len.
    """
    errors: list[str] = []
    warnings: list[str] = []

    tok_dir = Path(cfg.get("tokenizer_dir", "checkpoints/tokenizer"))
    prefix = cfg.get("tokenizer_prefix", "spm")
    model_file = tok_dir / f"{prefix}.model"
    if not model_file.exists():
        errors.append(f"tokenizer missing: {model_file} (run scripts/train_tokenizer.py)")

    tokens_dir = Path(data_cfg.tokens_dir)
    seq_len = int(cfg.model.max_seq_len)
    names = [s["name"] for s in sources]
    if not names:
        errors.append(f"no sources present on disk under {data_cfg.raw_dir}")

    have_train = 0
    for name in names:
        tr = tokens_dir / f"train_{name}.npy"
        va = tokens_dir / f"val_{name}.npy"
        if not tr.exists():
            errors.append(f"missing token stream {tr} (run scripts/tokenize_dataset.py)")
            continue
        have_train += 1
        n = _stream_len(tr)
        if n < seq_len + 2:
            errors.append(f"train stream '{name}' has {n} tokens < seq_len+2 "
                          f"({seq_len + 2}); can't form a single training window")
        if (not va.exists()) or _stream_len(va) <= seq_len:
            warnings.append(f"val stream '{name}' yields 0 windows at seq_len "
                            f"{seq_len}; its validation perplexity will be empty")
    if names and have_train == 0:
        errors.append(f"no train_*.npy streams in {tokens_dir}")

    # Tokenizer is the source of truth for vocab; uint16 streams need <= 65536.
    if model_file.exists():
        try:
            from lloom.tokenizer import SPTokenizer
            tv = SPTokenizer(tok_dir, prefix).vocab_size
            if tv > 65536:
                errors.append(f"tokenizer vocab {tv} > 65536 won't fit uint16 streams")
            floor = int(cfg.model.get("vocab_size", 0))
            if floor > tv:
                warnings.append(f"model.vocab_size floor {floor} > tokenizer vocab "
                                f"{tv}: {floor - tv} embedding rows will never train "
                                f"(harmless, but lower the floor to save params)")
        except Exception as e:  # tokenizer present but unreadable
            warnings.append(f"could not load tokenizer to check vocab ({e})")

    return errors, warnings


def check_jsonl(paths, required=("prompt", "response"),
                aliases: dict | None = None) -> tuple[list[str], list[str], int]:
    """Validate JSONL line-by-line. `aliases` maps a required key to extra
    accepted keys, e.g. {"prompt": ("instruction", "question")}.
    Returns (errors, warnings, n_ok)."""
    errors: list[str] = []
    warnings: list[str] = []
    n_ok = 0
    alias = aliases or {}
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as e:
                    errors.append(f"{p}:{i} invalid JSON ({e})")
                    continue
                ok = all(any(row.get(x) for x in ((k,) + tuple(alias.get(k, ()))))
                         for k in required)
                if ok:
                    n_ok += 1
                else:
                    warnings.append(f"{p}:{i} missing one of {required}")
    return errors, warnings, n_ok
