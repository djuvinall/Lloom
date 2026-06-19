"""One object tying the eval suite together for any checkpoint."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import torch

from .clustering import clustering_eval
from .embed import embed_texts
from .perplexity import perplexity_on_stream
from .retrieval import retrieval_eval


class Evaluator:
    def __init__(self, model, tokenizer, device, batch_size=16, seq_len=1024):
        self.model, self.tok, self.device = model, tokenizer, device
        self.batch_size, self.seq_len = batch_size, seq_len

    def evaluate_perplexity(self, streams: dict[str, np.ndarray]) -> dict[str, float]:
        out, tot, n = {}, 0.0, 0
        for name, s in streams.items():
            ce, ntok = perplexity_on_stream(self.model, s, self.batch_size,
                                            self.seq_len, self.device)
            out[f"perplexity/{name}"] = math.exp(min(ce, 20))
            tot += ce * ntok; n += ntok
        out["perplexity/total"] = math.exp(min(tot / max(n, 1), 20))
        return out

    def evaluate_ood(self, texts: dict[str, str]) -> dict[str, float]:
        out = {}
        for name, text in texts.items():
            ids = np.array(self.tok.encode(text), dtype=np.int64)
            if len(ids) > self.seq_len + 1:
                ce, _ = perplexity_on_stream(self.model, ids, 4, self.seq_len,
                                             self.device)
                out[f"perplexity/ood_{name}"] = math.exp(min(ce, 20))
        return out

    def evaluate_retrieval(self, pairs: list[tuple[str, str]], k=10) -> dict:
        """MRR / NDCG@k / recall over (query, positive) pairs with in-batch
        distractors. Rule of thumb: contrastive-finetune only if MRR < 0.7."""
        m = retrieval_eval(self.model, self.tok, pairs, self.device, k,
                           self.batch_size)
        return {f"retrieval/{k_}": v for k_, v in m.items()}

    def evaluate_qa(self, qa_pairs: list[dict], out_path: str | Path,
                    prompt_fn, max_new_tokens=150, **gen_kw) -> dict:
        """Generate an answer per pair and write JSONL (question, reference,
        generated) for human accuracy/citation rating. prompt_fn(question) ->
        prompt string is supplied by the project (templating is its job)."""
        from ..infer.generate import generate
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for pair in qa_pairs:
            prompt = prompt_fn(pair["question"])
            idx = torch.tensor([self.tok.encode(prompt)], device=self.device)
            out = generate(self.model, idx, max_new_tokens,
                           eot_id=self.tok.eot_id, **gen_kw)
            gen_text = self.tok.decode(out[0, idx.shape[1]:].tolist())
            rows.append({"question": pair["question"],
                         "reference": pair.get("answer", ""),
                         "generated": gen_text})
        with open(out_path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return {"qa/n_generated": len(rows), "qa/output": str(out_path)}

    def evaluate_clustering(self, texts: list[str], k: int,
                            labels: list[int] | None = None) -> dict:
        emb = embed_texts(self.model, self.tok, texts, self.device, self.batch_size)
        m = clustering_eval(emb, k,
                            torch.tensor(labels) if labels is not None else None)
        return {f"clustering/{k_}": v for k_, v in m.items()}
