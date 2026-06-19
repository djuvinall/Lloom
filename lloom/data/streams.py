"""Token streams + curriculum-weighted multi-source sampling.

Streams are uint16 .npy memmaps (one per source per split): a many-GB corpus
is a few-MB RAM footprint and resume costs nothing. "Source" is whatever the
project says it is - a language, a domain, or a data source.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch


def load_token_streams(tokens_dir: str | Path, split: str,
                       source_names: list[str]) -> dict[str, np.ndarray]:
    out = {}
    for name in source_names:
        p = Path(tokens_dir) / f"{split}_{name}.npy"
        if p.exists():
            out[name] = np.load(p, mmap_mode="r")
    if not out:
        raise FileNotFoundError(
            f"No '{split}' streams in {tokens_dir} - tokenize the dataset first")
    return out


class MixtureSchedule:
    """Phase-based curriculum over tiered sources, phases as fractions of
    max_steps. Tier weights split equally inside a tier across sources actually
    present; absent tiers renormalize away. weights: 'uniform' = equal/source.
    """

    def __init__(self, curriculum_cfg, sources_present, max_steps: int):
        self.max_steps = max_steps
        self.phases = curriculum_cfg["phases"]
        self.tiers: dict[str, list[str]] = {}
        for s in sources_present:
            self.tiers.setdefault(s["tier"], []).append(s["name"])
        self.names = [s["name"] for s in sources_present]

    def target_weights(self, step: int) -> dict[str, float]:
        frac = min(step / max(self.max_steps, 1), 1.0)
        weights = next(p["weights"] for p in self.phases if frac < p["until"]
                       or p is self.phases[-1])
        if weights == "uniform":
            return {n: 1.0 / len(self.names) for n in self.names}
        per = {}
        for tier, tier_w in weights.items():
            for n in self.tiers.get(tier, []):
                per[n] = tier_w / len(self.tiers[tier])
        total = sum(per.values())          # < 1.0 if a tier has no sources
        return {n: w / total for n, w in per.items()}


class WeightedStreamSampler:
    """Per-sequence source sampling, deterministic in (seed, step, micro)."""

    def __init__(self, streams: dict[str, np.ndarray],
                 schedule: MixtureSchedule, seq_len: int, seed: int):
        self.streams = streams
        self.schedule = schedule
        self.seq_len = seq_len
        self.seed = seed
        self.names = list(streams)
        self.realized = {n: 0 for n in self.names}   # cumulative tokens served per source
        self.ema_share = None                        # windowed source mix for divergence
        self.ema_alpha = 0.02                        # EMA factor (~50-step window)

    def get_batch(self, step: int, micro: int, batch_size: int, device):
        gen = torch.Generator().manual_seed(self.seed + step * 64 + micro)
        w = self.schedule.target_weights(step)
        probs = torch.tensor([w.get(n, 0.0) for n in self.names])
        sidx = torch.multinomial(probs, batch_size, replacement=True, generator=gen)

        xs, ys, sources = [], [], []
        counts = {n: 0 for n in self.names}
        for i in sidx.tolist():
            name = self.names[i]
            s = self.streams[name]
            off = torch.randint(0, len(s) - self.seq_len - 1, (1,), generator=gen).item()
            win = torch.from_numpy(s[off:off + self.seq_len + 1].astype(np.int64))
            xs.append(win[:-1]); ys.append(win[1:]); sources.append(name)
            self.realized[name] += self.seq_len
            counts[name] += 1
        bsz = sum(counts.values()) or 1               # windowed source mix (EMA) for divergence
        frac = {n: counts[n] / bsz for n in self.names}
        if self.ema_share is None:
            self.ema_share = frac
        else:
            a = self.ema_alpha
            self.ema_share = {n: (1 - a) * self.ema_share[n] + a * frac[n] for n in self.names}
        x = torch.stack(xs).to(device, non_blocking=True)
        y = torch.stack(ys).to(device, non_blocking=True)
        return x, y, sources

    def distribution_report(self, step: int) -> tuple[dict, float]:
        """Recent (EMA windowed) source share vs target; max abs divergence
        drives the alert. Windowed rather than cumulative so the metric tracks
        the current curriculum phase instead of lagging it across phase
        boundaries (cumulative share false-alarmed at every weight shift)."""
        target = self.schedule.target_weights(step)
        shares = self.ema_share or {n: 0.0 for n in self.names}
        max_div = max(abs(shares.get(n, 0.0) - target.get(n, 0.0)) for n in self.names)
        return shares, max_div

    def reset_counters(self):
        self.realized = {n: 0 for n in self.names}
