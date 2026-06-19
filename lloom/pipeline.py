"""Pipeline runner: chain stage scripts from a YAML recipe.

A recipe is project-defined (lloom doesn't know what the stages do):

    name: pretrain
    stages:
      - name: prepare_data
        cmd: [scripts/prepare_data.py, --download]
      - name: pretrain
        cmd: [scripts/pretrain.py]
        pass_overrides: true        # forward --preset / --set to this stage
        skip_if: checkpoints/tokenizer/spm.model   # example: skip when present

Stages run as subprocesses of the current interpreter, fail-fast, with
timing and a final summary. --from/--until/--only select stages by name, so
a broken run resumes where it died. Combined with presets + --set overrides,
one recipe produces arbitrarily many different models:

    python scripts/run_pipeline.py --pipeline config/pipelines/pretrain.yaml \
        --preset large --set training.optimizer=muon
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import yaml


def load_recipe(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        recipe = yaml.safe_load(f)
    assert recipe.get("stages"), f"recipe {path} has no stages"
    return recipe


def _select(stages: list[dict], only=None, from_=None, until=None) -> list[dict]:
    names = [s["name"] for s in stages]
    for ref in filter(None, [only, from_, until]):
        if ref not in names:
            raise KeyError(f"stage {ref!r} not in recipe (have {names})")
    if only:
        return [s for s in stages if s["name"] == only]
    lo = names.index(from_) if from_ else 0
    hi = names.index(until) + 1 if until else len(stages)
    return stages[lo:hi]


def run_pipeline(recipe_path: str | Path, preset: str | None = None,
                 sets: list[str] | None = None, only: str | None = None,
                 from_: str | None = None, until: str | None = None,
                 dry_run: bool = False) -> None:
    recipe = load_recipe(recipe_path)
    stages = _select(recipe["stages"], only, from_, until)
    forwarded = ([f"--preset={preset}"] if preset else []) + \
                [f"--set={s}" for s in (sets or [])]
    print(f"pipeline {recipe.get('name', recipe_path)}: "
          f"{' -> '.join(s['name'] for s in stages)}"
          + (f" | forwarding {' '.join(forwarded)}" if forwarded else ""))

    results = []
    for stage in stages:
        cmd = [sys.executable] + [str(c) for c in stage["cmd"]]
        if stage.get("pass_overrides") and forwarded:
            cmd += forwarded
        skip = stage.get("skip_if")
        if skip and Path(skip).exists():
            print(f"[{stage['name']}] skipped ({skip} exists)")
            results.append((stage["name"], "skipped", 0.0))
            continue
        print(f"[{stage['name']}] $ {' '.join(cmd)}")
        if dry_run:
            results.append((stage["name"], "dry-run", 0.0))
            continue
        t0 = time.time()
        proc = subprocess.run(cmd)
        dt = time.time() - t0
        if proc.returncode != 0:
            results.append((stage["name"], f"FAILED ({proc.returncode})", dt))
            _summary(results)
            sys.exit(f"pipeline stopped at stage '{stage['name']}' - fix and "
                     f"resume with --from {stage['name']}")
        results.append((stage["name"], "ok", dt))
    _summary(results)


def _summary(results: list[tuple[str, str, float]]) -> None:
    width = max((len(n) for n, _, _ in results), default=4)
    print("\n=== pipeline summary ===")
    for name, status, dt in results:
        print(f"  {name:<{width}}  {status:<12} {dt:>8.1f}s")
