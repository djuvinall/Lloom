"""Optimizers: AdamW (default), Muon, Lion - selected by `training.optimizer`.

Muon (momentum + Newton-Schulz orthogonalization, Jordan et al.) is applied
only where it is defined: 2D hidden weight matrices. Embeddings, the LM head,
norms, and other <2D params always train under AdamW. The two are wrapped in a
MultiOptimizer that exposes a single optimizer surface to the trainer.

Every param group carries `base_lr`; the trainer multiplies it by the schedule
factor each step, so mixed-LR setups (Muon 0.02 / AdamW 6e-4) share one
schedule shape.
"""
from __future__ import annotations

import torch


def zeropower_via_newtonschulz5(G: torch.Tensor, steps: int = 5) -> torch.Tensor:
    """Quintic Newton-Schulz iteration approximating UV^T from G = USV^T.
    Coefficients (3.4445, -4.7750, 2.0315) tuned for fast convergence; runs in
    bf16 on CUDA (the iteration is robust to low precision)."""
    assert G.ndim == 2
    a, b, c = 3.4445, -4.7750, 2.0315
    X = G.bfloat16() if G.is_cuda else G.float()
    transposed = G.size(0) > G.size(1)
    if transposed:
        X = X.mT
    X = X / (X.norm() + 1e-7)
    for _ in range(steps):
        A = X @ X.mT
        B = b * A + c * A @ A
        X = a * X + B @ X
    if transposed:
        X = X.mT
    return X.to(G.dtype)


class Muon(torch.optim.Optimizer):
    def __init__(self, params, lr=0.02, momentum=0.95, nesterov=True,
                 ns_steps=5, weight_decay=0.0):
        super().__init__(params, dict(lr=lr, momentum=momentum, nesterov=nesterov,
                                      ns_steps=ns_steps, weight_decay=weight_decay))

    @torch.no_grad()
    def step(self, closure=None):
        loss = closure() if closure is not None else None
        for group in self.param_groups:
            lr, mom = group["lr"], group["momentum"]
            for p in group["params"]:
                if p.grad is None:
                    continue
                g = p.grad
                state = self.state[p]
                if "momentum_buffer" not in state:
                    state["momentum_buffer"] = torch.zeros_like(g)
                buf = state["momentum_buffer"]
                buf.mul_(mom).add_(g)
                g = g.add(buf, alpha=mom) if group["nesterov"] else buf
                u = zeropower_via_newtonschulz5(g, group["ns_steps"])
                if group["weight_decay"]:
                    p.mul_(1 - lr * group["weight_decay"])
                # scale so update RMS matches across aspect ratios
                p.add_(u, alpha=-lr * max(1.0, p.size(0) / p.size(1)) ** 0.5)
        return loss


class Lion(torch.optim.Optimizer):
    """Sign-momentum optimizer (Chen et al. 2023). ~1/3 the state of AdamW.
    Rule of thumb: lr ~ AdamW lr / 10, weight_decay x10."""

    def __init__(self, params, lr=1e-4, betas=(0.9, 0.99), weight_decay=0.0):
        super().__init__(params, dict(lr=lr, betas=betas, weight_decay=weight_decay))

    @torch.no_grad()
    def step(self, closure=None):
        loss = closure() if closure is not None else None
        for group in self.param_groups:
            lr, (b1, b2), wd = group["lr"], group["betas"], group["weight_decay"]
            for p in group["params"]:
                if p.grad is None:
                    continue
                state = self.state[p]
                if "exp_avg" not in state:
                    state["exp_avg"] = torch.zeros_like(p)
                m = state["exp_avg"]
                if wd:
                    p.mul_(1 - lr * wd)
                p.add_(torch.sign(m.mul(b1).add(p.grad, alpha=1 - b1)), alpha=-lr)
                m.mul_(b2).add_(p.grad, alpha=1 - b2)
        return loss


class MultiOptimizer:
    """Several optimizers behind one interface; param_groups concatenates the
    children's live group dicts so schedule updates propagate."""

    def __init__(self, *optimizers):
        self.optimizers = [o for o in optimizers if o is not None]

    @property
    def param_groups(self):
        return [g for o in self.optimizers for g in o.param_groups]

    def zero_grad(self, set_to_none=True):
        for o in self.optimizers:
            o.zero_grad(set_to_none=set_to_none)

    def step(self):
        for o in self.optimizers:
            o.step()

    def state_dict(self):
        return {"children": [o.state_dict() for o in self.optimizers]}

    def load_state_dict(self, sd):
        for o, s in zip(self.optimizers, sd["children"]):
            o.load_state_dict(s)


def _split_params(model):
    """(hidden 2D+, decay, no_decay). Hidden = >=2D weights that are not the
    embedding / LM head (matched by name) - the Muon domain."""
    hidden, decay, no_decay = [], [], []
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        if p.ndim >= 2 and "embed" not in name and "lm_head" not in name:
            hidden.append(p)
        elif p.ndim >= 2:
            decay.append(p)
        else:
            no_decay.append(p)
    return hidden, decay, no_decay


def build_optimizer(model, t_cfg):
    """t_cfg keys: optimizer (adamw|muon|lion), lr, weight_decay, betas, eps,
    muon_lr, muon_momentum. Each group gets base_lr for the schedule."""
    name = t_cfg.get("optimizer", "adamw")
    lr, wd = t_cfg["lr"], t_cfg.get("weight_decay", 0.0)
    betas = tuple(t_cfg.get("betas", (0.9, 0.95)))
    eps = t_cfg.get("eps", 1e-8)
    hidden, decay, no_decay = _split_params(model)
    fused = torch.cuda.is_available() and any(
        p.is_cuda for p in hidden + decay + no_decay)

    def adamw(groups):
        return torch.optim.AdamW(groups, betas=betas, eps=eps, fused=fused)

    if name == "adamw":
        opt = adamw([
            {"params": hidden + decay, "lr": lr, "base_lr": lr, "weight_decay": wd},
            {"params": no_decay, "lr": lr, "base_lr": lr, "weight_decay": 0.0}])
        return MultiOptimizer(opt)
    if name == "lion":
        lion_lr = t_cfg.get("lion_lr", lr / 3)
        opt = Lion([
            {"params": hidden + decay, "lr": lion_lr, "base_lr": lion_lr,
             "weight_decay": wd * 3},
            {"params": no_decay, "lr": lion_lr, "base_lr": lion_lr,
             "weight_decay": 0.0}])
        return MultiOptimizer(opt)
    if name == "muon":
        muon_lr = t_cfg.get("muon_lr", 0.02)
        muon = Muon([{"params": hidden, "lr": muon_lr, "base_lr": muon_lr,
                      "weight_decay": t_cfg.get("muon_weight_decay", wd)}],
                    momentum=t_cfg.get("muon_momentum", 0.95)) if hidden else None
        rest = adamw([
            {"params": decay, "lr": lr, "base_lr": lr, "weight_decay": wd},
            {"params": no_decay, "lr": lr, "base_lr": lr, "weight_decay": 0.0}])
        return MultiOptimizer(muon, rest)
    raise KeyError(f"unknown optimizer {name!r} (adamw | muon | lion)")
