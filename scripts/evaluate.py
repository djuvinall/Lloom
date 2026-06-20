"""Stage 4: evaluate any checkpoint. Perplexity (in-domain + OOD) always;
retrieval / generation / clustering run when their data files exist and their
config blocks are enabled.

Data formats (all optional; a held-out copy in data/test/ is preferred over
data/sft/, which is the SFT *training* set - evaluating generation there
flatters the model, so eval warns when it has to fall back to it):
  retrieval:  retrieval_pairs.jsonl  {"query": ..., "positive": ...}
  generation: *.jsonl                {"prompt": ..., "response": ...}
  clustering: themed.jsonl           {"text": ..., "theme": ...}

Usage: python scripts/evaluate.py --checkpoint runs/<name>/checkpoints/pretrain/best.pt
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from textlm.prep import present_sources
from textlm.sft import load_sft_pairs, sft_prompt
from lloom.config import add_config_args, load_config
from lloom.data import load_jsonl, load_token_streams
from lloom.eval import Evaluator
from lloom.infer import load_model
from lloom.tokenizer import SPTokenizer
from lloom.utils import get_device

SPECIAL_JSONL = ("retrieval_pairs.jsonl", "themed.jsonl")


def main():
    ap = argparse.ArgumentParser()
    add_config_args(ap, "config/eval_config.yaml")
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--data_config", default="config/data_config.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config, preset=args.preset, sets=args.sets)
    data_cfg = load_config(args.data_config)
    device = get_device(cfg.device)
    ckpt = args.checkpoint or cfg.checkpoint

    model = load_model(ckpt, device)
    tok = SPTokenizer(cfg.tokenizer_dir, cfg.get("tokenizer_prefix", "spm"))
    # Eval window can't exceed what the model was built for (RoPE / KV cache):
    # default to the model's own context, clamp any explicit override down.
    seq_len = min(cfg.get("seq_len") or model.cfg.max_seq_len, model.cfg.max_seq_len)
    ev = Evaluator(model, tok, device, cfg.batch_size, seq_len)
    results = {"checkpoint": str(ckpt)}
    out_dir = Path(cfg.get("out_dir", "logs"))
    out_dir.mkdir(parents=True, exist_ok=True)
    sft_dir = Path(data_cfg.sft_dir)
    test_dir = Path(data_cfg.get("test_dir", "data/test"))

    def pick(fname):
        """Prefer a held-out copy in data/test/ over training data/sft/."""
        for d in (test_dir, sft_dir):
            if (d / fname).exists():
                return d / fname
        return None

    if cfg.perplexity.enabled:
        names = [s["name"] for s in present_sources(data_cfg)]
        streams = load_token_streams(data_cfg.tokens_dir, "val", names)
        results.update(ev.evaluate_perplexity(streams))
    if cfg.perplexity.ood:
        texts = {Path(f).stem: (Path(data_cfg.ood_dir) / f).read_text(encoding="utf-8", errors="replace")
                 for f in data_cfg.get("ood_files", []) if (Path(data_cfg.ood_dir) / f).exists()}
        results.update(ev.evaluate_ood(texts))

    rp = pick("retrieval_pairs.jsonl")
    if cfg.retrieval.enabled and rp:
        rows = load_jsonl([rp])
        pairs = [(r["query"], r["positive"]) for r in rows]
        results.update(ev.evaluate_retrieval(pairs, k=cfg.retrieval.get("k", 10)))

    gen_dir = test_dir if (test_dir.exists() and any(
        p.name not in SPECIAL_JSONL for p in test_dir.glob("*.jsonl"))) else sft_dir
    gen_files = [p for p in gen_dir.glob("*.jsonl")
                 if p.name not in SPECIAL_JSONL] if gen_dir.exists() else []
    if cfg.qa.enabled and gen_files:
        if gen_dir == sft_dir:
            print(f"[warn] no held-out generation set in {test_dir} - QA eval runs "
                  f"on TRAINING data ({sft_dir}); treat scores as optimistic")
        rows = load_sft_pairs(gen_dir)[:cfg.qa.get("max_pairs", 300)]
        pairs = [{"question": r["prompt"], "answer": r["response"]} for r in rows]
        results.update(ev.evaluate_qa(pairs, str(out_dir / "generations.jsonl"),
                                      prompt_fn=sft_prompt,
                                      max_new_tokens=cfg.qa.get("max_new_tokens", 150)))

    tv = pick("themed.jsonl")
    if cfg.clustering.enabled and tv:
        rows = load_jsonl([tv])
        themes = sorted({r["theme"] for r in rows})
        labels = [themes.index(r["theme"]) for r in rows]
        results.update(ev.evaluate_clustering([r["text"] for r in rows],
                                              k=len(themes), labels=labels))

    print(json.dumps(results, indent=2))
    (out_dir / "eval_results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
