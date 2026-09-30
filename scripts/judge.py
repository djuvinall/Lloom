"""Stage 4b: LLM-as-judge. Grade a run's generations with Claude or a local model.

Reads what evaluate.py generated (runs/<run>/eval/generations.jsonl: question,
reference, generated), asks a judge model for a 0..max_score score per row
against the rubric in config/judge_config.yaml, and writes

  runs/<run>/eval/judgements.jsonl    one verdict per row (score, justification, error)
  runs/<run>/eval/judge_results.json  the summary (mean score, pass rate, counts)

Any JSONL/JSON list of {prompt|question, response|generated, reference?} rows
works as --input, and --out names the summary file for ad-hoc use.

Usage:
  python scripts/judge.py --set run_name=my-run
  python scripts/judge.py --set provider=ollama --set model=qwen3:1.7b
  python scripts/judge.py --input items.json --out results.json --set max_items=20

Exits non-zero when nothing could be judged (bad credentials, no server, no
input), so a pipeline stops here rather than reporting an empty score.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lloom.config import add_config_args, load_config
from lloom.judge import DEFAULT_RUBRIC, JudgeError, judge_items, make_judge


def read_items(path: Path) -> list:
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("["):
        data = json.loads(text)
        if not isinstance(data, list):
            raise SystemExit(f"{path} is not a JSON list")
        return data
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main():
    ap = argparse.ArgumentParser()
    add_config_args(ap, "config/judge_config.yaml")
    ap.add_argument("--input", default=None, help="JSONL or JSON list to judge; default: config input")
    ap.add_argument("--out", default=None,
                    help="summary JSON path; judgements.jsonl is written beside it")
    args = ap.parse_args()
    cfg = load_config(args.config, preset=args.preset, sets=args.sets)
    # Verdicts quote model output; never let a console code page crash the run.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")

    src = Path(args.input or cfg.input)
    if not src.exists():
        sys.exit(f"nothing to judge: {src} does not exist - run evaluate.py for this "
                 f"run first, or pass --input")
    items = read_items(src)
    if not items:
        sys.exit(f"nothing to judge: {src} is empty")

    out = Path(args.out) if args.out else Path(cfg.out_dir) / "judge_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    verdict_path = out.with_name("judgements.jsonl") if not args.out \
        else out.with_suffix(".jsonl")

    judge = make_judge(cfg.provider, cfg.get("model"), effort=cfg.get("effort"),
                       fallbacks=bool(cfg.get("fallbacks", True)),
                       url=cfg.get("ollama_url") or "http://127.0.0.1:11434")
    threshold = cfg.get("pass_threshold")
    n = min(len(items), cfg.get("max_items") or len(items))
    print(f"judging {n} of {len(items)} item(s) from {src} with "
          f"{judge.provider}:{judge.model}")

    def show(v):
        mark = f"{v.score:g}" if v.score is not None else f"error: {v.error}"
        print(f"  [{v.index + 1}/{n}] {mark}", flush=True)

    try:
        result = judge_items(items, judge, rubric=cfg.get("rubric") or DEFAULT_RUBRIC,
                             max_score=int(cfg.get("max_score", 10)),
                             pass_threshold=threshold, max_items=cfg.get("max_items"),
                             on_verdict=show)
    except JudgeError as exc:
        sys.exit(f"judge stopped: {exc}")

    with open(verdict_path, "w", encoding="utf-8") as f:
        for v in result["verdicts"]:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")
    summary = dict(result["summary"], input=str(src), verdicts=str(verdict_path))
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if summary["n_scored"] == 0:
        sys.exit("judge produced no scores - every item failed; see the errors above")


if __name__ == "__main__":
    main()
