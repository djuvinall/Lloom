"""LLM-as-judge without a model: the request goes out, the verdicts come back.

This module never calls a model. **Which model grades, and where it runs, is
HollowDeck's business**: a graph's Model node names it (``ollama:qwen3.5:9b`` on your
own server, a hosted model once HollowDeck has that provider), HollowDeck's own
``model/structured`` node makes the call with a JSON schema, and the Ollama address is
one core setting (``HDECK_OLLAMA_URL``) rather than something every module carries.
So Lloom judging reads::

    Lloom Generate --results--> Lloom Judge Request --instructions/prompt/schema--> Structured (model/structured)
                                        |                                                  |
                                        +--items--> Lloom Judge Scores <----data-----------+

:func:`build_request` turns items and a rubric into the three texts the structured
call needs, and :func:`score` matches the answer back to the items, clamps and
aggregates, and names every item the model left out. Pure functions, stdlib only.
"""

from __future__ import annotations

import json
import statistics
from typing import Any

DEFAULT_RUBRIC = (
    "Judge whether the response answers the task correctly, completely and coherently. "
    "Reward responses that are factually right, on topic and fluent. Penalise responses "
    "that are wrong, off topic, repetitive, truncated, or that contradict the reference "
    "answer when one is given."
)

_PROMPT_KEYS = ("prompt", "question", "instruction", "input", "task")
_RESPONSE_KEYS = ("response", "completion", "generated", "output", "text")
_REFERENCE_KEYS = ("reference", "reference_answer", "expected", "answer", "target")

MAX_ITEMS = 200


class GradingError(ValueError):
    """The request or the answer cannot be used; the sentence says why."""


def unwrap(value: Any) -> Any:
    """The plain JSON under HollowDeck's bundle wire form (``{"$bundle": {...}}``),
    at any depth, and JSON typed as text parsed."""
    if isinstance(value, dict):
        if set(value) == {"$bundle"} and isinstance(value["$bundle"], dict):
            return unwrap(value["$bundle"])
        return {k: unwrap(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unwrap(v) for v in value]
    if isinstance(value, str):
        text = value.strip()
        if text[:1] in ("{", "["):
            try:
                return unwrap(json.loads(text))
            except ValueError:
                pass
    return value


def _first(row: dict, keys: tuple) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return ""


def normalize_items(value: Any) -> list[dict]:
    """``[{prompt, response, reference}]`` from any accepted spelling: Lloom Generate's
    results, the evaluator's ``question/reference/generated``, SFT-style pairs, a
    single object, JSON text or JSONL."""
    value = unwrap(value)
    if value in (None, "", []):
        return []
    if isinstance(value, str):
        rows = []
        for line in value.splitlines():
            if line.strip():
                try:
                    rows.append(unwrap(json.loads(line)))
                except ValueError:
                    raise GradingError(f"items: not JSON or JSONL: {line[:60]!r}") from None
        value = rows
    if isinstance(value, dict):
        value = value.get("items") if isinstance(value.get("items"), list) else [value]
    if not isinstance(value, list):
        raise GradingError(f"items must be a list of objects, got {type(value).__name__}")
    out = []
    for row in value:
        if isinstance(row, str):
            out.append({"prompt": "", "response": row, "reference": ""})
        elif isinstance(row, dict):
            out.append({"prompt": _first(row, _PROMPT_KEYS),
                        "response": _first(row, _RESPONSE_KEYS),
                        "reference": _first(row, _REFERENCE_KEYS)})
        else:
            raise GradingError(f"an item must be an object or a string, got {type(row).__name__}")
    return out


def verdict_schema(max_score: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item": {"type": "integer", "description": "the item's number"},
                        "score": {"type": "integer",
                                  "description": f"0 (fails entirely) to {max_score} (fully meets the rubric)"},
                        "justification": {"type": "string",
                                          "description": "one or two sentences"},
                    },
                    "required": ["item", "score", "justification"],
                },
            },
        },
        "required": ["verdicts"],
    }


def build_request(items: list[dict], rubric: str = "", max_score: int = 10) -> dict:
    """The instructions, prompt and schema for one structured call grading every item."""
    if not items:
        raise GradingError("nothing to judge: give items, or a response")
    if len(items) > MAX_ITEMS:
        raise GradingError(f"{len(items)} items is too many for one request (at most {MAX_ITEMS})")
    if max_score < 1:
        raise GradingError("max_score must be at least 1")
    rubric = (rubric or "").strip() or DEFAULT_RUBRIC
    instructions = (
        "You grade responses written by a small language model that is being trained, so "
        "that its trainer can compare checkpoints. Grade every numbered item below against "
        f"the rubric, and only against it. Give each an integer score from 0 to {max_score}: "
        f"0 means the response fails the task entirely or is empty, and {max_score} means it "
        "fully meets the rubric. A reference answer, when given, shows what a good answer "
        "contains; it need not be matched word for word. Give each a justification of one "
        "or two sentences naming what earned or cost points. Return one verdict per item, "
        "with the item's number.\n\n"
        f"Rubric:\n{rubric}"
    )
    blocks = []
    for number, item in enumerate(items, start=1):
        parts = [f'<item number="{number}">']
        if item["prompt"]:
            parts.append(f"<task>\n{item['prompt']}\n</task>")
        if item["reference"]:
            parts.append(f"<reference_answer>\n{item['reference']}\n</reference_answer>")
        parts.append(f"<response>\n{item['response']}\n</response>")
        parts.append("</item>")
        blocks.append("\n".join(parts))
    prompt = (f"Grade these {len(items)} item(s).\n\n" + "\n\n".join(blocks))
    return {"instructions": instructions, "prompt": prompt,
            "schema": json.dumps(verdict_schema(max_score)), "items": items,
            "count": len(items)}


def _clamp(raw: Any, max_score: int) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        try:
            raw = float(str(raw).strip())
        except (TypeError, ValueError):
            raise ValueError(f"the score is not a number: {raw!r}") from None
    return float(min(max(raw, 0), max_score))


def parse_verdicts(value: Any) -> list[dict]:
    """The verdict list from what the structured call returned: its ``data`` bundle, the
    object, the bare list, or the JSON text."""
    data = unwrap(value)
    if isinstance(data, dict):
        data = data.get("verdicts")
    if not isinstance(data, list):
        raise GradingError("the model's answer has no verdicts list; wire the structured "
                           "node's data (or its text) into verdicts")
    return [v for v in data if isinstance(v, dict)]


def score(items: list[dict], verdicts: list[dict], *, max_score: int = 10,
          pass_threshold: float | None = None, provider: str = "", model: str = "") -> dict:
    """Match verdicts to items by number; ``{"verdicts": [...], "summary": {...}}``."""
    by_number: dict[int, dict] = {}
    for verdict in verdicts:
        try:
            number = int(verdict.get("item"))
        except (TypeError, ValueError):
            continue
        by_number.setdefault(number, verdict)
    rows = []
    for number, item in enumerate(items, start=1):
        row = dict(item, index=number - 1, score=None, justification="", passed=None, error=None)
        verdict = by_number.get(number)
        if verdict is None:
            row["error"] = "the model returned no verdict for this item"
        else:
            try:
                row["score"] = _clamp(verdict.get("score"), max_score)
                row["justification"] = str(verdict.get("justification") or "").strip()
            except ValueError as exc:
                row["error"] = str(exc)
        if row["score"] is not None and pass_threshold is not None:
            row["passed"] = row["score"] >= pass_threshold
        rows.append(row)
    scores = [r["score"] for r in rows if r["score"] is not None]
    summary = {
        "provider": provider, "model": model,
        "n_items": len(rows), "n_scored": len(scores),
        "n_errors": sum(1 for r in rows if r["error"]),
        "max_score": max_score,
        "mean_score": round(statistics.fmean(scores), 4) if scores else None,
        "mean_score_norm": round(statistics.fmean(scores) / max_score, 4) if scores else None,
        "pass_threshold": pass_threshold,
        "pass_rate": (round(sum(1 for s in scores if s >= pass_threshold) / len(scores), 4)
                      if scores and pass_threshold is not None else None),
        "extra_verdicts": sorted(n for n in by_number if not 1 <= n <= len(items)),
    }
    return {"verdicts": rows, "summary": summary}
