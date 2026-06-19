"""Supervised finetuning loop over packed prompt/response batches.

Works identically for full finetuning and LoRA (the script decides which
params are trainable before handing the model over; build_optimizer only sees
requires_grad params). Epoch-based with step-level eval/early-stop, same
checkpoint/logging conventions as the pretrainer.
"""
from __future__ import annotations

import time
from pathlib import Path

import torch

from .optim import build_optimizer
from .schedules import build_schedule
from ..data.sft import block_causal_mask
from ..utils import CSVLogger, WandbLogger


class SFTTrainer:
    def __init__(self, cfg, model, train_batches: list, val_batches: list, device):
        self.cfg, self.model, self.device = cfg, model, device
        self.train_batches, self.val_batches = train_batches, val_batches
        t = cfg.training
        self.max_steps = t.get("max_steps") or t.epochs * max(
            len(train_batches) // t.get("grad_accum_steps", 1), 1)
        t["max_steps"] = self.max_steps          # schedule needs it resolved
        self.opt = build_optimizer(model, t)
        self.schedule = build_schedule(t)
        self.autocast = torch.autocast(
            device_type=device.type, dtype=torch.bfloat16,
            enabled=(device.type == "cuda" and t.get("precision", "bf16") == "bf16"))
        self.out_dir = Path(cfg.out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.csv = CSVLogger(cfg.logging.csv_path)
        run = cfg.get("run_name") or f"sft-{time.strftime('%Y%m%d-%H%M%S')}"
        self.wandb = WandbLogger(cfg.logging.wandb.enabled,
                                 cfg.logging.wandb.project, run, dict(cfg))
        self.step, self.best_val, self.no_improve = 0, float("inf"), 0

    def _to_device(self, batch):
        x, y, doc = (batch[k].to(self.device, non_blocking=True)
                     for k in ("x", "y", "doc"))
        return x, y, block_causal_mask(doc)

    def train(self):
        t = self.cfg.training
        accum = t.get("grad_accum_steps", 1)
        n_trainable = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        print(f"sft: {self.max_steps} steps | {len(self.train_batches)} batches/epoch "
              f"| trainable {n_trainable / 1e6:.2f}M params")
        gen = torch.Generator().manual_seed(self.cfg.get("seed", 0))
        order = []
        self.model.train()
        while self.step < self.max_steps:
            self.opt.zero_grad(set_to_none=True)
            mult = self.schedule(self.step)
            for g in self.opt.param_groups:
                g["lr"] = g["base_lr"] * mult
            total = 0.0
            for _ in range(accum):
                if not order:                      # reshuffle each epoch
                    order = torch.randperm(len(self.train_batches),
                                           generator=gen).tolist()
                x, y, mask = self._to_device(self.train_batches[order.pop()])
                with self.autocast:
                    _, loss = self.model(x, y, mask=mask)
                (loss / accum).backward()
                total += loss.item()
            gnorm = torch.nn.utils.clip_grad_norm_(self.model.parameters(),
                                                   t.get("grad_clip", 1.0))
            self.opt.step()
            self.step += 1

            if self.step % self.cfg.logging.log_interval == 0:
                m = {"loss/train": total / accum, "grad_norm": float(gnorm),
                     "lr": self.opt.param_groups[0]["lr"]}
                self.csv.log(self.step, m); self.wandb.log(m, self.step)
                print(f"step {self.step:>5} loss {m['loss/train']:.4f} lr {m['lr']:.2e}")
            if self.step % self.cfg.evaluation.eval_interval == 0:
                if self._validate():
                    print(f"early stop at {self.step}"); break
        self._save("last.pt"); self.wandb.finish()

    @torch.no_grad()
    def _validate(self) -> bool:
        self.model.eval()
        tot, n = 0.0, 0
        for batch in self.val_batches:
            x, y, mask = self._to_device(batch)
            with self.autocast:
                _, loss = self.model(x, y, mask=mask)
            k = (y != -100).sum().item()
            tot += loss.item() * k; n += k
        val = tot / max(n, 1)
        m = {"loss/val": val}
        self.csv.log(self.step, m); self.wandb.log(m, self.step)
        print(f"  val {val:.4f} (best {self.best_val:.4f})")
        self.model.train()
        if val < self.best_val:
            self.best_val, self.no_improve = val, 0
            self._save("best.pt")
        else:
            self.no_improve += 1
        es = self.cfg.early_stopping
        return es.enabled and self.no_improve >= es.patience

    def _save(self, name: str):
        raw = getattr(self.model, "_orig_mod", self.model)
        torch.save({"model": raw.state_dict(), "step": self.step,
                    "best_val": self.best_val, "model_cfg": raw.cfg.__dict__},
                   self.out_dir / name)
