"""LR schedules as multiplier functions: step -> factor in (0, 1].

Multipliers (not absolute LRs) so one schedule drives optimizers whose param
groups have different base LRs (e.g. Muon hidden weights at 0.02 next to
AdamW embeddings at 6e-4). Trainer applies: lr = group.base_lr * mult(step).

  cosine   - warmup, then cosine decay to min_fraction (the classic).
  wsd      - warmup-stable-decay: flat at 1.0, linear decay over the final
             decay_fraction of training. Extend max_steps mid-run without
             changing the loss trajectory of the stable phase.
  linear   - warmup, then linear decay to min_fraction.
  constant - warmup, then flat.
"""
from __future__ import annotations

import math
from typing import Callable


def _warmup(step: int, warmup: int) -> float | None:
    if step < warmup:
        return (step + 1) / max(warmup, 1)
    return None


def cosine(step, max_steps, warmup, min_fraction=0.1, **_):
    w = _warmup(step, warmup)
    if w is not None:
        return w
    t = (step - warmup) / max(max_steps - warmup, 1)
    return min_fraction + (1 - min_fraction) * 0.5 * (1 + math.cos(math.pi * min(t, 1.0)))

def wsd(step, max_steps, warmup, min_fraction=0.1, decay_fraction=0.2, **_):
    w = _warmup(step, warmup)
    if w is not None:
        return w
    decay_start = max_steps * (1 - decay_fraction)
    if step < decay_start:
        return 1.0
    t = (step - decay_start) / max(max_steps - decay_start, 1)
    return 1.0 - (1.0 - min_fraction) * min(t, 1.0)

def linear(step, max_steps, warmup, min_fraction=0.1, **_):
    w = _warmup(step, warmup)
    if w is not None:
        return w
    t = (step - warmup) / max(max_steps - warmup, 1)
    return 1.0 - (1.0 - min_fraction) * min(t, 1.0)

def constant(step, max_steps, warmup, **_):
    w = _warmup(step, warmup)
    return 1.0 if w is None else w


SCHEDULES: dict[str, Callable] = {
    "cosine": cosine, "wsd": wsd, "linear": linear, "constant": constant,
}


def build_schedule(t_cfg) -> Callable[[int], float]:
    """t_cfg: training config block (schedule, max_steps, warmup_steps,
    min_lr_fraction, wsd_decay_fraction)."""
    name = t_cfg.get("schedule", "cosine")
    if name not in SCHEDULES:
        raise KeyError(f"unknown schedule {name!r}; have {sorted(SCHEDULES)}")
    fn = SCHEDULES[name]
    kw = dict(max_steps=t_cfg["max_steps"], warmup=t_cfg.get("warmup_steps", 0),
              min_fraction=t_cfg.get("min_lr_fraction", 0.1),
              decay_fraction=t_cfg.get("wsd_decay_fraction", 0.2))
    return lambda step: fn(step, **kw)
