"""Generic supervised-finetuning (instruction) data: prompt/response templating
around lloom's SFT packing.

Data: data/sft/*.jsonl with {"prompt": ..., "response": ...} per line. Common
aliases are accepted: instruction/input -> prompt, output/answer/completion ->
response. The template uses dedicated special tokens for a clean response
trigger:

  <|prompt|> Summarize photosynthesis. <|response|> Plants convert ... <|endoftext|>
"""
from __future__ import annotations

from pathlib import Path

from lloom.data.sft import load_jsonl

_PROMPT_KEYS = ("prompt", "instruction", "question")
_RESPONSE_KEYS = ("response", "output", "completion", "answer")


def _first(row: dict, keys) -> str | None:
    for k in keys:
        if row.get(k):
            return row[k]
    return None


def sft_prompt(prompt: str) -> str:
    return f"<|prompt|> {prompt.strip()} <|response|>"


def load_sft_pairs(sft_dir, pattern: str = "*.jsonl") -> list[dict]:
    paths = sorted(Path(sft_dir).glob(pattern))
    if not paths:
        raise FileNotFoundError(
            f"no {pattern} in {sft_dir} - add SFT data before finetuning")
    rows, dropped = [], 0
    for r in load_jsonl(paths):
        p, resp = _first(r, _PROMPT_KEYS), _first(r, _RESPONSE_KEYS)
        if p and resp:
            rows.append({"prompt": p, "response": resp})
        else:
            dropped += 1
    msg = f"loaded {len(rows)} SFT pairs from {len(paths)} file(s)"
    if dropped:
        msg += f" - dropped {dropped} row(s) missing a prompt or response"
    print(msg)
    if not rows:
        raise ValueError(
            f"no usable SFT pairs in {sft_dir} (every row missing prompt/response?)")
    return rows


def encode_sft_pairs(tokenizer, rows: list[dict]) -> list[tuple[list[int], list[int]]]:
    """-> (prompt_ids, response_ids); response carries the EOT so the model
    learns to stop. Loss is masked to the response by lloom.data.sft."""
    out = []
    for r in rows:
        prompt = tokenizer.encode(sft_prompt(r["prompt"]))
        resp = tokenizer.encode(" " + r["response"].strip()) + [tokenizer.eot_id]
        out.append((prompt, resp))
    return out
