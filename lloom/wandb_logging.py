"""Weights & Biases logging, isolated from the default code path.

Everything wandb lives here, gated behind the WANDB_ENABLED environment
variable: unless it is set to a truthy value ("1", "true", "yes", "on"),
constructing a WandbLogger performs no wandb import, no network call, and no
wandb.init() - the logger is a pure no-op. Local CSV logging
(lloom.utils.CSVLogger) is always on and never depends on this module.

Enable per run:

    WANDB_ENABLED=1 python scripts/pretrain.py ...

or pass --wandb to a stage script, which sets WANDB_ENABLED=1 for the process.
"""
from __future__ import annotations

import os

_TRUTHY = ("1", "true", "yes", "on")


def wandb_enabled() -> bool:
    """Single gate for all wandb activity; unset or falsy means fully inert."""
    return os.environ.get("WANDB_ENABLED", "").strip().lower() in _TRUTHY


class WandbLogger:
    """No-op unless WANDB_ENABLED is truthy and wandb is importable/logged in -
    training never blocks on a logging service."""

    def __init__(self, project: str, run_name: str, config: dict):
        self.run = None
        if not wandb_enabled():
            return
        try:
            import wandb
            self.run = wandb.init(project=project, name=run_name, config=config)
        except Exception as e:  # offline, not installed, not logged in
            print(f"[wandb] disabled ({e})")

    def log(self, metrics: dict, step: int) -> None:
        if self.run is not None:
            self.run.log(metrics, step=step)

    def log_text(self, key: str, text: str, step: int) -> None:
        if self.run is not None:
            import wandb
            self.run.log({key: wandb.Html(f"<pre>{text}</pre>")}, step=step)

    def finish(self) -> None:
        if self.run is not None:
            self.run.finish()
