"""Pretraining loop: checkpoint/resume, mixture-sampler monitoring,
multi-objective mixing, val + OOD evals, sample generation, CSV + WandB
logging. Project-agnostic: anything corpus-specific arrives through the
sampler, tokenizer, and config.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import torch

from . import objectives
from .optim import build_optimizer
from .schedules import build_schedule
from ..eval.perplexity import perplexity_on_stream
from ..utils import CSVLogger, WandbLogger, load_rng_state, rng_state


class Trainer:
    def __init__(self, cfg, model, sampler, val_streams, tokenizer,
                 device, ood_texts: dict[str, str] | None = None):
        self.cfg, self.model, self.sampler = cfg, model, sampler
        self.val_streams, self.tok, self.device = val_streams, tokenizer, device
        self.ood_texts = ood_texts or {}

        t = cfg.training
        self.opt = build_optimizer(model, t)
        self.schedule = build_schedule(t)
        self.autocast = torch.autocast(
            device_type=device.type, dtype=torch.bfloat16,
            enabled=(device.type == "cuda" and t.precision == "bf16"))

        self.step, self.best_val, self.no_improve = 0, float("inf"), 0
        self.out_dir = Path(cfg.out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.csv = CSVLogger(cfg.logging.csv_path)
        run = cfg.run_name or f"run-{time.strftime('%Y%m%d-%H%M%S')}"
        self.wandb = WandbLogger(cfg.logging.wandb.enabled, cfg.logging.wandb.project,
                                 run, dict(cfg))
        self.ema = {objectives.CAUSAL: None, objectives.SPAN: None}
        self.mix = cfg.get("objectives") or {"causal_lm_prob": 1.0}

        if t.get("compile"):
            self.model = torch.compile(self.model)

    # ---------------------------------------------------------------- loop
    def train(self):
        t = self.cfg.training
        seq_len = self.cfg.model.max_seq_len
        tokens_per_step = t.batch_size * t.grad_accum_steps * seq_len
        print(f"training: {t.max_steps} steps x {tokens_per_step} tok "
              f"= {t.max_steps * tokens_per_step / 1e6:.0f}M tokens "
              f"| opt {t.get('optimizer', 'adamw')} "
              f"| sched {t.get('schedule', 'cosine')}")
        self.model.train()
        t0 = time.time()

        while self.step < t.max_steps:
            self.opt.zero_grad(set_to_none=True)
            mult = self.schedule(self.step)
            for g in self.opt.param_groups:
                g["lr"] = g["base_lr"] * mult

            losses, counts = {}, {}
            for micro in range(t.grad_accum_steps):
                x, y, _ = self.sampler.get_batch(self.step, micro, t.batch_size,
                                                 self.device)
                obj = objectives.CAUSAL
                if self.mix.get("causal_lm_prob", 1.0) < 1.0:
                    obj = objectives.sample_objective(self.step, micro, self.cfg.seed,
                                                      self.mix["causal_lm_prob"])
                if obj == objectives.SPAN:
                    x, y = objectives.apply_span_corruption(
                        x, y, self.tok.mask_id, self.mix["span_mask_ratio"],
                        self.mix["span_mean_length"], self.step, micro,
                        self.cfg.seed)
                with self.autocast:
                    _, loss = self.model(x, y)
                (loss / t.grad_accum_steps).backward()
                losses[obj] = losses.get(obj, 0.0) + loss.item()
                counts[obj] = counts.get(obj, 0) + 1

            gnorm = torch.nn.utils.clip_grad_norm_(self.model.parameters(), t.grad_clip)
            self.opt.step()
            self.step += 1

            for k in losses:
                v = losses[k] / counts[k]
                self.ema[k] = v if self.ema[k] is None else 0.95 * self.ema[k] + 0.05 * v
            step_loss = sum(losses.values()) / sum(counts.values())

            if self.step % self.cfg.logging.log_interval == 0:
                self._log_train(step_loss, gnorm, tokens_per_step, t0); t0 = time.time()
            if self.step % self.cfg.evaluation.eval_interval == 0:
                stop = self._validate()
                self._save("last.pt")                              # resume point (with optimizer)
                self._save(f"step_{self.step}.pt", with_optim=False); self._rotate()
                if stop:
                    print(f"early stop at {self.step} (no improvement "
                          f"x{self.cfg.early_stopping.patience} evals)"); break
            if self.step % self.cfg.sampling.sample_interval == 0:
                self._samples()
        self._save("last.pt"); self.wandb.finish()

    # ------------------------------------------------------------- logging
    def _log_train(self, step_loss, gnorm, tokens_per_step, t0):
        dt = max(time.time() - t0, 1e-6)
        m = {"loss/total": step_loss,
             "lr": self.opt.param_groups[0]["lr"], "grad_norm": float(gnorm),
             "tokens_per_second": tokens_per_step * self.cfg.logging.log_interval / dt}
        for k, v in self.ema.items():
            if v is not None:
                m[f"loss/{k}"] = v
        raw = getattr(self.model, "_orig_mod", self.model)
        if getattr(raw, "aux_loss", None) is not None:
            m["loss/moe_aux"] = raw.aux_loss.item()
        if self.device.type == "cuda":
            m["gpu_memory_used_gb"] = torch.cuda.memory_allocated() / 1e9
        if hasattr(self.sampler, "distribution_report"):
            shares, max_div = self.sampler.distribution_report(self.step)
            m["sampler/max_divergence"] = max_div
            for n, s in shares.items():
                m[f"pct_tokens/source_{n}"] = s
            alert = self.cfg.get("divergence_alert", 0.05)
            if max_div > alert and sum(self.sampler.realized.values()) > 2e6:
                print(f"[warn] sampler divergence {max_div:.3f} > {alert} at {self.step}")
        self.csv.log(self.step, m); self.wandb.log(m, self.step)
        print(f"step {self.step:>6} loss {m['loss/total']:.4f} "
              f"lr {m['lr']:.2e} tok/s {m['tokens_per_second']:.0f}")

    @torch.no_grad()
    def _validate(self) -> bool:
        ev = self.cfg.evaluation
        tv = time.time()
        self.model.eval()
        m, tot, ntok = {}, 0.0, 0
        for name, stream in self.val_streams.items():
            ce, n = perplexity_on_stream(self.model, stream, self.cfg.training.batch_size,
                                         self.cfg.model.max_seq_len, self.device,
                                         max_batches=max(1, ev.val_batches // len(self.val_streams)))
            m[f"val/loss/source_{name}"] = ce
            m[f"val/perplexity/source_{name}"] = math.exp(min(ce, 20))
            tot += ce * n; ntok += n
        val = tot / max(ntok, 1)
        m["val/loss/total"], m["val/perplexity/total"] = val, math.exp(min(val, 20))

        if self.step % ev.ood_eval_interval == 0:
            for name, text in self.ood_texts.items():
                import numpy as np
                ids = np.asarray(self.tok.encode(text), dtype=np.int64)
                if len(ids) > self.cfg.model.max_seq_len + 1:
                    ce, _ = perplexity_on_stream(self.model, ids, 4,
                                                 self.cfg.model.max_seq_len,
                                                 self.device, max_batches=8)
                    m[f"val/perplexity/{name}"] = math.exp(min(ce, 20))

        self.csv.log(self.step, m); self.wandb.log(m, self.step)
        print(f"  val {val:.4f} ppl {m['val/perplexity/total']:.2f} "
              f"(best {self.best_val:.4f}) [{time.time() - tv:.1f}s]")
        self.model.train()
        if val < self.best_val:
            self.best_val, self.no_improve = val, 0
            self._save("best.pt", with_optim=False)
        else:
            self.no_improve += 1
        es = self.cfg.early_stopping
        return es.enabled and self.no_improve >= es.patience

    @torch.no_grad()
    def _samples(self):
        s = self.cfg.sampling
        out_dir = Path(self.cfg.logging.samples_dir); out_dir.mkdir(parents=True, exist_ok=True)
        raw = getattr(self.model, "_orig_mod", self.model)
        lines = []
        for i, prompt in enumerate(s.prompts):
            idx = torch.tensor([self.tok.encode(prompt)], device=self.device)
            out = raw.generate(idx, s.max_new_tokens, temperature=s.temperature,
                               top_p=s.top_p, eot_id=self.tok.eot_id)
            text = self.tok.decode(out[0].tolist())
            lines.append(f"--- prompt {i}: {prompt}\n{text}\n")
            self.wandb.log_text(f"samples/prompt_{i}", text, self.step)
        (out_dir / f"step_{self.step}.txt").write_text("\n".join(lines), encoding="utf-8")
        self.model.train()

    # ---------------------------------------------------------- checkpoints
    def _save(self, name: str, with_optim: bool = True):
        # Only last.pt needs optimizer state (the resume point); best.pt and the
        # rolling step_*.pt are model-only, which roughly halves checkpoint I/O.
        t0 = time.time()
        raw = getattr(self.model, "_orig_mod", self.model)   # un-compile
        ckpt = {"model": raw.state_dict(),
                "step": self.step, "best_val": self.best_val,
                "no_improve": self.no_improve,
                "model_cfg": raw.cfg.__dict__,
                "sampler_realized": getattr(self.sampler, "realized", {}),
                "rng": rng_state()}
        if with_optim:
            ckpt["optimizer"] = self.opt.state_dict()
        torch.save(ckpt, self.out_dir / name)
        print(f"  [ckpt] {name} "
              f"{(self.out_dir / name).stat().st_size / 1e6:.0f}MB in {time.time() - t0:.1f}s")
        manifest = self.out_dir / "manifest.json"
        hist = json.loads(manifest.read_text()) if manifest.exists() else []
        hist.append({"name": name, "step": self.step, "best_val": self.best_val})
        manifest.write_text(json.dumps(hist[-200:], indent=1))

    def _rotate(self):
        ckpts = sorted(self.out_dir.glob("step_*.pt"),
                       key=lambda p: int(p.stem.split("_")[1]))
        for p in ckpts[:-self.cfg.checkpoint.keep_last]:
            p.unlink()

    def resume(self, path: str | Path):
        ck = torch.load(path, map_location=self.device, weights_only=False)
        raw = getattr(self.model, "_orig_mod", self.model)
        raw.load_state_dict(ck["model"])
        if "optimizer" in ck:
            self.opt.load_state_dict(ck["optimizer"])
        else:
            print(f"  (no optimizer state in {path}; optimizer starts fresh)")
        self.step, self.best_val = ck["step"], ck["best_val"]
        self.no_improve = ck.get("no_improve", 0)
        if hasattr(self.sampler, "realized"):
            self.sampler.realized.update(ck.get("sampler_realized", {}))
        if "rng" in ck:
            load_rng_state(ck["rng"])
        print(f"resumed from {path} at step {self.step} (best val {self.best_val:.4f})")
