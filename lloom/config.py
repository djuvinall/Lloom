"""Config machinery: YAML + dot access + deep merge + presets + CLI overrides.

Merge order (later wins):  base config  <  preset  <  --set overrides
This is the whole "one config, many models" automation story: presets are
partial YAMLs (usually a `model:` block plus training adjustments), and
--set handles one-off tweaks without touching files.

Run identity: a config that carries a `run_name` key gets it resolved (null ->
default_run_name) and then ${run_name} is expanded throughout the tree, so
paths like runs/${run_name}/checkpoints namespace every run's artifacts.
"""
from __future__ import annotations

import copy
import re
import shutil
from pathlib import Path

import yaml

_VAR_RE = re.compile(r"\$\{(\w+)\}")


class Cfg(dict):
    """dict with attribute access, recursively wrapping nested dicts."""

    def __getattr__(self, key):
        try:
            v = self[key]
        except KeyError as e:
            raise AttributeError(key) from e
        if isinstance(v, dict) and not isinstance(v, Cfg):
            v = Cfg(v)
            self[key] = v       # store back so nested mutations persist
        return v

    def __setattr__(self, key, value):
        self[key] = value


def deep_merge(base: dict, override: dict) -> dict:
    """Recursive merge; `override` wins. Lists replace wholesale (predictable)."""
    out = copy.deepcopy(dict(base))
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _parse_value(raw: str):
    """YAML-parse, then rescue numerics YAML 1.1 treats as strings ('3e-4')."""
    v = yaml.safe_load(raw)
    if isinstance(v, str):
        for cast in (int, float):
            try:
                return cast(v)
            except ValueError:
                pass
    return v


def parse_overrides(sets: list[str] | None) -> dict:
    """['training.lr=3e-4', 'model.n_layers=24'] -> nested dict.
    Values are parsed, so `true`, `3e-4`, `[1,2]`, `null` all work."""
    out: dict = {}
    for s in sets or []:
        if "=" not in s:
            raise ValueError(f"--set expects key.path=value, got {s!r}")
        key, _, raw = s.partition("=")
        node = out
        parts = key.strip().split(".")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = _parse_value(raw)
    return out


def resolve_preset(preset: str | Path, preset_dir: str | Path = "config/presets") -> Path:
    """Accept a path ('config/presets/large.yaml') or a bare name ('large')."""
    p = Path(preset)
    if p.suffix in (".yaml", ".yml") or p.exists():
        return p
    cand = Path(preset_dir) / f"{preset}.yaml"
    if cand.exists():
        return cand
    raise FileNotFoundError(f"preset {preset!r} not found (looked for {cand})")


def default_run_name(cfg: dict) -> str:
    """Resolve the identity that namespaces a run's artifacts (option B).

    Returns a stable name ("default") so a pretrain -> sft -> release sequence
    invoked under one run_name all lands in runs/<run_name>/... and downstream
    stages can find upstream outputs. Override per run with
    `--set run_name=my-model` (or `run_pipeline --run-name my-model`).

    Option C hook: for automatic, collision-proof namespacing without manual
    names, return a fingerprint of the resolved config (+ data) here, e.g.

        import hashlib, yaml
        key = yaml.safe_dump(to_plain({k: cfg.get(k) for k in
              ("model", "training", "objectives")}), sort_keys=True)
        return "h" + hashlib.sha1(key.encode()).hexdigest()[:10]

    Everything else -- ${run_name} interpolation, pipeline forwarding, skip_if
    -- already threads whatever this returns through every path, so swapping
    the strategy here is the whole of option C.
    """
    return "default"


def interpolate_vars(cfg: dict) -> dict:
    """Substitute ${key} with top-level scalar config values, recursively.

    Lets paths be written once in terms of run identity, e.g.
        out_dir: runs/${run_name}/checkpoints/pretrain
    Only top-level str/int/float keys are exposed; unknown ${...} are left
    verbatim (never an error) so unrelated shell-style text survives."""
    scalars = {k: v for k, v in cfg.items() if isinstance(v, (str, int, float))}

    def sub(s: str) -> str:
        return _VAR_RE.sub(
            lambda m: str(scalars[m.group(1)]) if m.group(1) in scalars
            else m.group(0), s)

    def walk(o):
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v) for v in o]
        return sub(o) if isinstance(o, str) else o

    return walk(cfg)


def load_config(path: str | Path, preset: str | Path | None = None,
                sets: list[str] | None = None,
                preset_dir: str | Path = "config/presets",
                resolve: bool = True) -> Cfg:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    if preset:
        with open(resolve_preset(preset, preset_dir), "r", encoding="utf-8") as f:
            cfg = deep_merge(cfg, yaml.safe_load(f) or {})
    if sets:
        cfg = deep_merge(cfg, parse_overrides(sets))
    if resolve:
        # Resolve run identity (only for configs that opt in with a run_name
        # key), then expand ${run_name} and friends throughout the tree.
        if cfg.get("run_name", "_absent_") in (None, "", "null"):
            cfg["run_name"] = default_run_name(cfg)
        cfg = interpolate_vars(cfg)
    return Cfg(cfg)


def add_config_args(ap, default_config: str) -> None:
    """Standard config CLI surface shared by every stage script."""
    ap.add_argument("--config", default=default_config)
    ap.add_argument("--preset", default=None,
                    help="preset name (config/presets/{name}.yaml) or path")
    ap.add_argument("--set", dest="sets", action="append", default=[],
                    metavar="KEY.PATH=VALUE",
                    help="dotted config override, repeatable")
    ap.add_argument("--wandb", action="store_true",
                    help="enable Weights & Biases logging (off by default; local CSV always on)")


def to_plain(obj):
    """Recursively convert Cfg (and nested dict/list) to plain builtins.
    Nested values get lazily upgraded to Cfg on attribute access, so by the
    time a run snapshots its config the tree is full of Cfg objects that
    yaml.safe_dump refuses to represent. Flatten them back first."""
    if isinstance(obj, dict):
        return {k: to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_plain(v) for v in obj]
    return obj


def save_snapshot(config_paths: list[str | Path], out_dir: str | Path,
                  resolved: dict | None = None) -> None:
    """Copy source configs next to checkpoints; also dump the fully merged
    config (post-preset, post---set) so any run is exactly reproducible."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for p in config_paths:
        p = Path(p)
        if p.exists():
            shutil.copy(p, out / p.name)
    if resolved is not None:
        (out / "resolved_config.yaml").write_text(
            yaml.safe_dump(to_plain(resolved), sort_keys=False), encoding="utf-8")
