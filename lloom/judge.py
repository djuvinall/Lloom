"""LLM-as-judge: score model outputs against a rubric with Claude or a local model.

Project-agnostic like the rest of lloom: a caller supplies items (a prompt, the
response being judged, optionally a reference answer) and a rubric, and gets a
score per item plus a summary. Nothing here knows a corpus.

Two providers:

  anthropic  Claude, through the official `anthropic` SDK (an optional extra:
             pip install -e ".[judge]"). Imported only when this provider is
             used. Credentials resolve the SDK's usual way: ANTHROPIC_API_KEY,
             ANTHROPIC_AUTH_TOKEN, or an `ant auth login` profile.
  ollama     A local model served by Ollama, over plain HTTP on loopback
             (stdlib only). Nothing leaves the machine.

Both ask for the same JSON verdict, {"score": int, "justification": str}, using
each provider's structured-output mode, so a verdict is parsed, never scraped.

Importing this module pulls in no torch and no SDK.
"""
from __future__ import annotations

import json
import statistics
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable

PROVIDERS = ("anthropic", "ollama")
DEFAULT_MODELS = {"anthropic": "claude-opus-5-5", "ollama": "qwen3:1.7b"}
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"

DEFAULT_RUBRIC = (
    "Judge whether the response answers the task correctly, completely and "
    "coherently. Reward responses that are factually right, on topic and fluent. "
    "Penalise responses that are wrong, off topic, repetitive, truncated, or that "
    "contradict the reference answer when one is given."
)

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer"},
        "justification": {"type": "string"},
    },
    "required": ["score", "justification"],
    "additionalProperties": False,
}

# Field aliases, so evaluator output (question/reference/generated), SFT pairs
# (prompt/response) and ad-hoc items all read without a conversion step.
_PROMPT_KEYS = ("prompt", "question", "instruction", "input")
_RESPONSE_KEYS = ("response", "generated", "completion", "output", "text")
_REFERENCE_KEYS = ("reference", "answer", "expected", "target")


class JudgeError(RuntimeError):
    """A failure that makes judging pointless for every item (bad credentials,
    a missing SDK, an unreachable server) rather than for one item."""


@dataclass
class Verdict:
    index: int
    prompt: str
    response: str
    reference: str
    score: float | None = None
    justification: str = ""
    passed: bool | None = None
    error: str | None = None
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _first(row: dict, keys: Iterable[str]) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def normalize_item(row: Any) -> dict:
    """{prompt, response, reference} from any of the accepted spellings."""
    if isinstance(row, str):
        return {"prompt": "", "response": row, "reference": ""}
    if not isinstance(row, dict):
        raise ValueError(f"a judge item must be an object or a string, got {type(row).__name__}")
    return {
        "prompt": _first(row, _PROMPT_KEYS),
        "response": _first(row, _RESPONSE_KEYS),
        "reference": _first(row, _REFERENCE_KEYS),
    }


def system_prompt(max_score: int) -> str:
    return (
        "You grade responses written by a small language model that is being "
        "trained, so that its trainer can compare checkpoints. Grade only against "
        f"the rubric. Give an integer score from 0 to {max_score}: 0 means the "
        f"response fails the task entirely and {max_score} means it fully meets the "
        "rubric. A reference answer, when given, shows what a good answer contains; "
        "it need not be matched word for word. Return the score and a justification "
        "of one or two sentences that names what earned or cost points."
    )


def user_prompt(item: dict, rubric: str) -> str:
    parts = [f"<rubric>\n{rubric.strip()}\n</rubric>"]
    if item["prompt"]:
        parts.append(f"<task>\n{item['prompt']}\n</task>")
    if item["reference"]:
        parts.append(f"<reference_answer>\n{item['reference']}\n</reference_answer>")
    parts.append(f"<response>\n{item['response']}\n</response>")
    return "\n\n".join(parts)


class AnthropicJudge:
    """Claude through the official SDK, with a JSON-schema output format.

    `fallbacks="default"` (beta server-side-fallback-2026-07-01) re-runs a request
    that a safety classifier declined on Anthropic's recommended fallback model
    instead of returning the refusal; it is on by default and `fallbacks=False`
    turns it off (it is not accepted for every model). `effort` goes in
    output_config; pass None for a model that takes no effort setting.
    """

    provider = "anthropic"

    def __init__(self, model: str | None = None, *, effort: str | None = "medium",
                 fallbacks: bool = True, max_tokens: int = 16000, max_retries: int = 4,
                 client: Any = None):
        self.model = model or DEFAULT_MODELS["anthropic"]
        self.effort = effort or None
        self.fallbacks = fallbacks
        self.max_tokens = max_tokens
        if client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise JudgeError(
                    "the anthropic provider needs the anthropic SDK in this "
                    "interpreter: pip install -e \".[judge]\"") from exc
            client = anthropic.Anthropic(max_retries=max_retries)
        self.client = client

    def grade(self, system: str, user: str) -> dict:
        output_config: dict = {"format": {"type": "json_schema", "schema": VERDICT_SCHEMA}}
        if self.effort:
            output_config["effort"] = self.effort
        kwargs: dict = dict(model=self.model, max_tokens=self.max_tokens, system=system,
                            messages=[{"role": "user", "content": user}],
                            output_config=output_config)
        if self.fallbacks:
            kwargs["betas"] = ["server-side-fallback-2026-07-01"]
            kwargs["fallbacks"] = "default"
        response = self._call(kwargs)
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise ValueError(f"the model declined to grade this item ({category or 'refusal'})")
        if response.stop_reason == "max_tokens":
            raise ValueError("the verdict was cut off at max_tokens")
        text = next((b.text for b in response.content if b.type == "text"), "")
        return json.loads(text)

    def _call(self, kwargs: dict):
        try:
            import anthropic
        except ImportError:  # an injected client without the SDK installed (tests)
            return self.client.beta.messages.create(**kwargs)
        try:
            return self.client.beta.messages.create(**kwargs)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise JudgeError(f"Claude refused the credentials: {exc.message}") from exc
        except anthropic.NotFoundError as exc:
            raise JudgeError(f"model {self.model!r} was not found: {exc.message}") from exc
        except anthropic.RateLimitError as exc:
            # The SDK already retried with backoff; what reaches here is persistent.
            raise ValueError(f"rate limited after retries: {exc.message}") from exc
        except anthropic.BadRequestError as exc:
            raise ValueError(f"bad request: {exc.message}") from exc
        except anthropic.APIStatusError as exc:
            raise ValueError(f"API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise JudgeError(f"cannot reach the Claude API: {exc}") from exc


class OllamaJudge:
    """A local model served by Ollama: POST /api/chat with a JSON-schema format."""

    provider = "ollama"

    def __init__(self, model: str | None = None, *, url: str = DEFAULT_OLLAMA_URL,
                 timeout: float = 180.0, opener: Callable | None = None):
        self.model = model or DEFAULT_MODELS["ollama"]
        self.url = url.rstrip("/")
        self.timeout = timeout
        self._open = opener or urllib.request.urlopen

    def grade(self, system: str, user: str) -> dict:
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "stream": False,
            "format": VERDICT_SCHEMA,
            "options": {"temperature": 0},
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{self.url}/api/chat", data=body, method="POST",
            headers={"content-type": "application/json"})
        try:
            with self._open(request, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code == 404:
                raise JudgeError(f"ollama has no model {self.model!r} (ollama pull "
                                 f"{self.model}): {detail}") from exc
            raise ValueError(f"ollama answered {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise JudgeError(f"cannot reach ollama at {self.url}: {exc.reason}") from exc
        return json.loads((payload.get("message") or {}).get("content") or "")


def make_judge(provider: str = "anthropic", model: str | None = None, **kwargs):
    provider = (provider or "anthropic").strip().lower()
    if provider == "anthropic":
        allowed = ("effort", "fallbacks", "max_tokens", "max_retries", "client")
        return AnthropicJudge(model, **{k: v for k, v in kwargs.items() if k in allowed})
    if provider == "ollama":
        allowed = ("url", "timeout", "opener")
        return OllamaJudge(model, **{k: v for k, v in kwargs.items() if k in allowed})
    raise ValueError(f"unknown judge provider {provider!r}; known: {', '.join(PROVIDERS)}")


def _clamp_score(raw: Any, max_score: int) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"the verdict's score is not a number: {raw!r}")
    return float(min(max(raw, 0), max_score))


def judge_items(items: Iterable[Any], judge, *, rubric: str = DEFAULT_RUBRIC,
                max_score: int = 10, pass_threshold: float | None = None,
                max_items: int | None = None,
                on_verdict: Callable[[Verdict], None] | None = None) -> dict:
    """Grade each item; one item's failure is recorded on that item, never raised.

    A JudgeError (credentials, a missing SDK, an unreachable server) stops the run,
    because it would fail every remaining item the same way. Returns
    {"summary": {...}, "verdicts": [Verdict.to_dict(), ...]}.
    """
    if max_score < 1:
        raise ValueError("max_score must be at least 1")
    system = system_prompt(max_score)
    verdicts: list[Verdict] = []
    for index, row in enumerate(items):
        if max_items is not None and index >= max_items:
            break
        item = normalize_item(row)
        verdict = Verdict(index=index, **item)
        started = time.monotonic()
        if not item["response"].strip():
            verdict.score = 0.0
            verdict.justification = "empty response"
        else:
            try:
                raw = judge.grade(system, user_prompt(item, rubric))
                verdict.score = _clamp_score(raw.get("score"), max_score)
                verdict.justification = str(raw.get("justification", "")).strip()
            except JudgeError:
                raise
            except (ValueError, KeyError, AttributeError, TypeError) as exc:
                verdict.error = str(exc) or type(exc).__name__
        verdict.seconds = round(time.monotonic() - started, 3)
        if verdict.score is not None and pass_threshold is not None:
            verdict.passed = verdict.score >= pass_threshold
        verdicts.append(verdict)
        if on_verdict is not None:
            on_verdict(verdict)
    return {"summary": summarize(verdicts, judge, max_score, pass_threshold),
            "verdicts": [v.to_dict() for v in verdicts]}


def summarize(verdicts: list[Verdict], judge, max_score: int,
              pass_threshold: float | None) -> dict:
    scores = [v.score for v in verdicts if v.score is not None]
    summary = {
        "provider": getattr(judge, "provider", ""),
        "model": getattr(judge, "model", ""),
        "n_items": len(verdicts),
        "n_scored": len(scores),
        "n_errors": sum(1 for v in verdicts if v.error),
        "max_score": max_score,
        "mean_score": round(statistics.fmean(scores), 4) if scores else None,
        "mean_score_norm": round(statistics.fmean(scores) / max_score, 4) if scores else None,
        "pass_threshold": pass_threshold,
        "pass_rate": None,
    }
    if pass_threshold is not None and scores:
        summary["pass_rate"] = round(sum(1 for s in scores if s >= pass_threshold) / len(scores), 4)
    return summary
