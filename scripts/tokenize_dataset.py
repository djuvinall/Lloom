"""Stage 0c: encode processed text into uint16 token streams, with a train/val
split at document granularity.
Usage: python scripts/tokenize_dataset.py
"""
import argparse
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lloom.config import load_config
from lloom.tokenizer import SPTokenizer

EOT = "<|endoftext|>"


def document_chunks(text: str) -> list[str]:
    """Split processed text into documents on the <|endoftext|> marker."""
    chunks, cur = [], []
    for line in text.splitlines():
        cur.append(line)
        if line.strip() == EOT:
            chunks.append("\n".join(cur)); cur = []
    if cur and any(l.strip() for l in cur):
        chunks.append("\n".join(cur))
    return chunks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/data_config.yaml")
    ap.add_argument("--tokenizer_dir", default="checkpoints/tokenizer")
    ap.add_argument("--tokenizer_prefix", default="spm")
    args = ap.parse_args()
    cfg = load_config(args.config)
    tok = SPTokenizer(args.tokenizer_dir, args.tokenizer_prefix)
    out = Path(cfg.tokens_dir); out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(cfg.split.seed)

    for txt in sorted(Path(cfg.text_dir).glob("*.txt")):
        name = txt.stem
        chunks = document_chunks(txt.read_text(encoding="utf-8"))
        val_ids = set(i for i in range(len(chunks)) if rng.random() < cfg.split.val_fraction)
        tr = [t for i, c in enumerate(chunks) if i not in val_ids for t in tok.encode(c)]
        va = [t for i, c in enumerate(chunks) if i in val_ids for t in tok.encode(c)]
        assert tok.vocab_size <= 65536, "uint16 streams need vocab <= 65536"
        np.save(out / f"train_{name}.npy", np.asarray(tr, dtype=np.uint16))
        np.save(out / f"val_{name}.npy", np.asarray(va, dtype=np.uint16))
        print(f"{name}: train {len(tr):,} tok | val {len(va):,} tok "
              f"({len(val_ids)}/{len(chunks)} docs held out)")


if __name__ == "__main__":
    main()
