"""Batch generation from a checkpoint, JSON in / JSON out - for automation.

serve.py is the interactive surface; this is the scriptable one: give it prompts,
get completions back as JSON, and exit. The HollowDeck module's `generate` tool
runs it, and a judge (scripts/judge.py) can read what it writes.

Checkpoint: --checkpoint wins; otherwise the newest finished stage of the run,
looked for in this order under runs/<run_name>/checkpoints/:
sft_lora/merged.pt, sft_full/best.pt, pretrain/best.pt.

Usage:
  python scripts/generate.py --prompt "Once upon a time"
  python scripts/generate.py --run_name my-run --chat --prompt "Explain gravity."
  python scripts/generate.py --prompts_file prompts.json --out completions.json

--prompts_file takes a JSON list of strings or objects with a "prompt" key, or
JSONL of the same. --chat wraps each prompt in the SFT template
(<|prompt|> ... <|response|>) that instruction-tuned checkpoints expect.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CHECKPOINT_ORDER = ("sft_lora/merged.pt", "sft_full/best.pt", "pretrain/best.pt")


def resolve_checkpoint(checkpoint: str | None, run_name: str) -> Path:
    if checkpoint:
        path = Path(checkpoint)
        if not path.exists():
            sys.exit(f"checkpoint {path} does not exist")
        return path
    base = Path("runs") / run_name / "checkpoints"
    for rel in CHECKPOINT_ORDER:
        if (base / rel).exists():
            return base / rel
    sys.exit(f"run {run_name!r} has no finished checkpoint under {base} "
             f"(looked for {', '.join(CHECKPOINT_ORDER)}); pass --checkpoint")


def read_prompts(args) -> list[str]:
    prompts = list(args.prompt or [])
    if args.prompts_file:
        text = Path(args.prompts_file).read_text(encoding="utf-8")
        rows = json.loads(text) if text.lstrip().startswith("[") else \
            [json.loads(line) for line in text.splitlines() if line.strip()]
        for row in rows:
            if isinstance(row, str):
                prompts.append(row)
            elif isinstance(row, dict) and isinstance(row.get("prompt"), str):
                prompts.append(row["prompt"])
            else:
                sys.exit(f"{args.prompts_file}: every row must be a string or have a "
                         f"string 'prompt'; got {row!r:.80}")
    if not prompts:
        sys.exit("no prompts: pass --prompt and/or --prompts_file")
    return prompts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--run_name", default="default")
    ap.add_argument("--prompt", action="append", default=[], help="repeatable")
    ap.add_argument("--prompts_file", default=None)
    ap.add_argument("--out", default=None, help="write the JSON here as well as stdout")
    ap.add_argument("--chat", action="store_true", help="wrap prompts in the SFT template")
    ap.add_argument("--tokenizer_dir", default="checkpoints/tokenizer")
    ap.add_argument("--tokenizer_prefix", default="spm")
    ap.add_argument("--device", default="auto", help="auto | cpu | cuda")
    ap.add_argument("--max_new_tokens", type=int, default=150)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--top_p", type=float, default=0.9)
    ap.add_argument("--top_k", type=int, default=0)
    ap.add_argument("--min_p", type=float, default=0.05)
    ap.add_argument("--repetition_penalty", type=float, default=1.2)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    prompts = read_prompts(args)
    ckpt = resolve_checkpoint(args.checkpoint, args.run_name)

    import torch

    from lloom.infer import generate, load_model
    from lloom.tokenizer import SPTokenizer
    from textlm.sft import sft_prompt

    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available()
                          else ("cpu" if args.device == "auto" else args.device))
    started = time.time()
    model = load_model(ckpt, device)
    tok = SPTokenizer(args.tokenizer_dir, args.tokenizer_prefix)
    results = []
    for i, prompt in enumerate(prompts):
        text = sft_prompt(prompt) if args.chat else prompt
        idx = torch.tensor([tok.encode(text)], device=device)
        out = generate(model, idx, args.max_new_tokens, temperature=args.temperature,
                       top_k=args.top_k, top_p=args.top_p, min_p=args.min_p,
                       repetition_penalty=args.repetition_penalty, eot_id=tok.eot_id,
                       seed=None if args.seed is None else args.seed + i)
        new_ids = out[0, idx.shape[1]:].tolist()
        if tok.eot_id in new_ids:
            new_ids = new_ids[:new_ids.index(tok.eot_id)]
        results.append({"prompt": prompt, "input": text,
                        "completion": tok.decode(new_ids).strip(),
                        "n_tokens": len(new_ids)})
    payload = {"checkpoint": str(ckpt).replace("\\", "/"), "device": str(device),
               "seconds": round(time.time() - started, 3), "results": results}
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                  encoding="utf-8")
    # ASCII-escaped on stdout: a model can emit anything, and a Windows console's
    # code page cannot print everything (the file above keeps the real characters).
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
