"""Generic text-domain data prep: normalize raw text sources into clean,
document-segmented text for tokenization. This is the project-specific half of
Stage 0; the tokenizer/stream machinery it feeds is lloom's.

Raw input:  data/raw/{name}.txt   - free text; blank lines separate documents
                                    (a file with no blank lines = one doc/line).
Output:     data/processed/text/{name}.txt - normalized, documents joined by
                                    the <|endoftext|> marker.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

from lloom.config import Cfg

EOT = "<|endoftext|>"


def present_sources(data_cfg) -> list[Cfg]:
    """Sources whose raw file actually exists on disk (weights renormalize over
    whatever is present, so a partial corpus just works)."""
    raw = Path(data_cfg.raw_dir)
    return [Cfg(s) for s in data_cfg.sources if (raw / f"{s['name']}.txt").exists()]


def all_special_tokens(tok_cfg) -> list[str]:
    """Configured special tokens + reserved slots for future task tokens."""
    toks = list(tok_cfg.special_tokens)
    toks += [f"<|reserved_{i}|>" for i in range(tok_cfg.get("reserved_token_slots", 0))]
    return toks


def _documents(raw: str) -> list[str]:
    """Split raw text into documents. Blank lines delimit documents; a file with
    no blank-line structure falls back to one document per non-empty line."""
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    blocks = [b.strip() for b in raw.split("\n\n")]
    blocks = [b for b in blocks if b]
    if len(blocks) <= 1:
        blocks = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    return blocks


def normalize_text(name: str, raw_path: Path, out_path: Path) -> int:
    """Raw text -> NFC-normalized lines, whitespace collapsed, documents
    separated by <|endoftext|>. Returns the document count."""
    raw = unicodedata.normalize("NFC", raw_path.read_text(encoding="utf-8", errors="replace"))
    out: list[str] = []
    docs = _documents(raw)
    for d in docs:
        for ln in d.splitlines():
            ln = " ".join(ln.split())
            if ln:
                out.append(ln)
        out.append(EOT)
    out_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return len(docs)
