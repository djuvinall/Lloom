"""End-to-end smoke test of the *actual* CLI scripts on a tiny synthetic corpus:
prepare_data -> train_tokenizer -> tokenize_dataset -> preflight -> pretrain ->
evaluate, nano preset on CPU in seconds. Unlike test_lloom.py (framework units
on synthetic tensors), this exercises the real stage wiring and the run-name
namespaced path handoffs between stages - the seams unit tests don't cover.

Runs in a throwaway copy of the repo so it never touches your real data/ or
runs/. Skips cleanly if torch / sentencepiece aren't installed.

  python tests/test_scripts_smoke.py      # or: pytest tests/test_scripts_smoke.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_WORDS = ("the quick brown fox jumps over a lazy dog river mountain cloud sky "
          "stone water light wind fire earth forest valley ocean desert silver "
          "golden ancient quiet morning shadow harbor lantern copper meadow "
          "thunder willow ember crimson hollow drifting").split()


def _have(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


def _synthetic_corpus(seed: int = 0) -> str:
    """120 varied blank-line-separated docs: enough tokens/pieces for a small
    SentencePiece vocab and several seq_len=64 windows per split."""
    rng = random.Random(seed)
    docs = []
    for _ in range(120):
        n = rng.randint(8, 22)
        docs.append(" ".join(rng.choice(_WORDS) for _ in range(n)).capitalize() + ".")
    return "\n\n".join(docs)


def run_smoke(tmp: str) -> None:
    work = Path(tmp) / "repo"
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(
        ".git", "runs", "checkpoints", "logs", "wandb", "__pycache__",
        "*.egg-info", ".venv", "venv", ".pytest_cache", "data"))

    # Fresh, self-contained data tree (data/ was excluded from the copy).
    (work / "data/raw").mkdir(parents=True)
    (work / "data/raw/sample.txt").write_text(_synthetic_corpus(), encoding="utf-8")
    (work / "data/sft").mkdir(parents=True)
    shutil.copy(ROOT / "data/sft/sample.jsonl", work / "data/sft/sample.jsonl")

    # Size the tokenizer for the tiny corpus. 16000 is too high (too few pieces);
    # byte_fallback reserves 256 + alphabet + specials needs >313, so 300 is too
    # low. 512 sits comfortably between the floor and this corpus's ceiling (~792).
    tok_cfg = work / "config/tokenizer_config.yaml"
    tok_cfg.write_text(tok_cfg.read_text().replace("vocab_size: 16000", "vocab_size: 512"))

    env = dict(os.environ, PYTHONPATH=str(work))

    def run(*cmd: str) -> None:
        print("  +", " ".join(cmd))
        subprocess.run([sys.executable, *cmd], cwd=work, env=env, check=True)

    common = ["--preset", "nano", "--set", "device=cpu", "--set", "model.max_seq_len=64"]
    run("scripts/prepare_data.py")
    run("scripts/train_tokenizer.py")
    run("scripts/tokenize_dataset.py")
    run("scripts/preflight.py", *common)
    run("scripts/pretrain.py", *common,
        "--set", "training.max_steps=2", "--set", "training.batch_size=2",
        "--set", "training.grad_accum_steps=1", "--set", "evaluation.eval_interval=1",
        "--set", "evaluation.val_batches=1", "--set", "sampling.sample_interval=100",
        "--set", "checkpoint.save_interval=1", "--set", "logging.log_interval=1")

    best = work / "runs/default/checkpoints/pretrain/best.pt"
    assert best.exists(), f"pretrain did not produce {best}"

    run("scripts/evaluate.py", *common,
        "--checkpoint", "runs/default/checkpoints/pretrain/best.pt",
        "--set", "qa.max_new_tokens=8", "--set", "qa.max_pairs=2")

    res = work / "runs/default/eval/eval_results.json"
    assert res.exists(), f"evaluate did not write {res}"
    data = json.loads(res.read_text())
    assert "perplexity/total" in data, data       # evaluate.py keys perplexity by source/total
    print("ok scripts smoke (prepare -> tokenizer -> tokenize -> preflight -> "
          "pretrain -> evaluate; runs/ namespacing intact)")


def test_scripts_smoke() -> None:
    if not (_have("torch") and _have("sentencepiece")):
        print("SKIP scripts smoke (needs torch + sentencepiece)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        run_smoke(tmp)


if __name__ == "__main__":
    test_scripts_smoke()
