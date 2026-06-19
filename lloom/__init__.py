"""lloom - a config-driven LLM training framework.

Project-agnostic: nothing in this package knows about any particular corpus,
model, or repo. A project supplies YAML configs + thin CLI scripts; lloom
supplies the machinery (model zoo, trainers, finetuning, inference, eval,
quantization, pipeline automation).

Deliberately lightweight at import time: importing `lloom` pulls in no torch.
Heavy subpackages (lloom.model, lloom.train, ...) are imported explicitly.
"""
__version__ = "0.1.0"

from .config import Cfg, deep_merge, load_config, parse_overrides, save_snapshot

__all__ = ["Cfg", "deep_merge", "load_config", "parse_overrides", "save_snapshot",
           "__version__"]
