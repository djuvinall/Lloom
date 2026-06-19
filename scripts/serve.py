"""Stage 5b: local inference server (FastAPI + SSE streaming).

  python scripts/serve.py --checkpoint checkpoints/pretrain/best.pt
  python scripts/serve.py --checkpoint checkpoints/export/model_int8.pt --int8

  curl -s localhost:8000/health
  curl -s localhost:8000/generate -d '{"prompt": "Once upon a time"}' \
       -H 'content-type: application/json'
  curl -sN localhost:8000/generate -d '{"prompt": "Once upon a time", "stream": true}' \
       -H 'content-type: application/json'
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lloom.infer import load_model
from lloom.infer.server import build_app
from lloom.quant import load_quantized
from lloom.tokenizer import SPTokenizer
from lloom.utils import get_device


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default="checkpoints/pretrain/best.pt")
    ap.add_argument("--tokenizer_dir", default="checkpoints/tokenizer")
    ap.add_argument("--tokenizer_prefix", default="spm")
    ap.add_argument("--int8", action="store_true",
                    help="checkpoint is a dynamic-int8 export (CPU)")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--top_p", type=float, default=0.9)
    ap.add_argument("--top_k", type=int, default=0)
    ap.add_argument("--min_p", type=float, default=0.05)
    ap.add_argument("--repetition_penalty", type=float, default=1.2)
    ap.add_argument("--max_new_tokens", type=int, default=200)
    args = ap.parse_args()

    if args.int8:
        model = load_quantized(args.checkpoint)
    else:
        model = load_model(args.checkpoint, get_device(args.device))
    tok = SPTokenizer(args.tokenizer_dir, args.tokenizer_prefix)
    app = build_app(model, tok, defaults={
        "temperature": args.temperature, "top_p": args.top_p, "top_k": args.top_k,
        "min_p": args.min_p, "repetition_penalty": args.repetition_penalty,
        "max_new_tokens": args.max_new_tokens})

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
