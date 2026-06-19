"""SentencePiece training + a thin runtime wrapper with stable special ids.

BPE with byte fallback by default: rare/unseen characters degrade to bytes
instead of <unk>, which matters as soon as a corpus is less curated than the
one the tokenizer was trained on. Special tokens are entirely config-driven;
the wrapper resolves the conventional pad/eot/mask trio if present.
"""
from __future__ import annotations

import json
from pathlib import Path

import sentencepiece as spm


def train_spm(input_files: list[str | Path], model_dir: str | Path,
              model_prefix: str, vocab_size: int, special_tokens: list[str],
              model_type: str = "bpe", character_coverage: float = 0.9995,
              byte_fallback: bool = True) -> Path:
    if not input_files:
        raise FileNotFoundError("no tokenizer input files")
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    prefix = model_dir / model_prefix
    spm.SentencePieceTrainer.train(
        input=",".join(str(p) for p in input_files),
        model_prefix=str(prefix),
        vocab_size=vocab_size,
        model_type=model_type,
        character_coverage=character_coverage,
        user_defined_symbols=special_tokens,
        byte_fallback=byte_fallback,
        pad_id=-1, bos_id=-1, eos_id=-1, unk_id=0,
        normalization_rule_name="nfkc",
    )
    (model_dir / "tokenizer_config.json").write_text(
        json.dumps({"special_tokens": special_tokens, "vocab_size": vocab_size,
                    "model_type": model_type, "byte_fallback": byte_fallback},
                   indent=2), encoding="utf-8")
    return prefix.with_suffix(".model")


class SPTokenizer:
    """Wrapper with the id helpers training code relies on. pad/eot/mask ids
    resolve to -1 when the corresponding special token is not in the vocab."""

    def __init__(self, model_dir: str | Path, model_prefix: str = "tokenizer",
                 pad_token: str = "<|pad|>", eot_token: str = "<|endoftext|>",
                 mask_token: str = "<|mask|>"):
        model_dir = Path(model_dir)
        self.sp = spm.SentencePieceProcessor(
            model_file=str(model_dir / f"{model_prefix}.model"))
        self.pad_id = self._maybe_id(pad_token)
        self.eot_id = self._maybe_id(eot_token)
        self.mask_id = self._maybe_id(mask_token)

    def _maybe_id(self, piece: str) -> int:
        tid = self.sp.piece_to_id(piece)
        return tid if tid != self.sp.unk_id() else -1

    @property
    def vocab_size(self) -> int:
        return self.sp.get_piece_size()

    def encode(self, text: str) -> list[int]:
        return self.sp.encode(text)

    def decode(self, ids: list[int]) -> str:
        return self.sp.decode([int(i) for i in ids])

    def token_id(self, piece: str) -> int:
        tid = self.sp.piece_to_id(piece)
        if tid == self.sp.unk_id() and piece != "<unk>":
            raise KeyError(f"{piece!r} not in vocab - retrain the tokenizer")
        return tid
