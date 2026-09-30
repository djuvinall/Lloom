"""lloom.judge: LLM-as-judge, with no network and no SDK.

Claude is exercised through an injected fake client (the request shape the SDK is
sent is the thing under test); Ollama through a fake urlopen. Torch-free, fast.
"""
from __future__ import annotations

import io
import json
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lloom.judge import (DEFAULT_MODELS, AnthropicJudge, JudgeError, OllamaJudge,
                         VERDICT_SCHEMA, judge_items, make_judge, normalize_item,
                         user_prompt)


class FakeJudge:
    provider, model = "fake", "fake-1"

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def grade(self, system, user):
        self.calls.append((system, user))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def _message(text="", stop_reason="end_turn", category=None):
    details = SimpleNamespace(category=category) if category else None
    return SimpleNamespace(stop_reason=stop_reason, stop_details=details,
                           content=[SimpleNamespace(type="text", text=text)])


def _client(response, sink):
    def create(**kwargs):
        sink.append(kwargs)
        return response
    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))


# -- items -------------------------------------------------------------------------

def test_normalize_item_reads_every_accepted_spelling():
    assert normalize_item({"question": "q", "generated": "g", "reference": "r"}) == \
        {"prompt": "q", "response": "g", "reference": "r"}
    assert normalize_item({"prompt": "p", "completion": "c"}) == \
        {"prompt": "p", "response": "c", "reference": ""}
    assert normalize_item("bare text")["response"] == "bare text"
    with pytest.raises(ValueError):
        normalize_item(42)


def test_user_prompt_leaves_out_an_absent_reference():
    text = user_prompt({"prompt": "p", "response": "r", "reference": ""}, "rubric")
    assert "<reference_answer>" not in text and "<response>\nr\n</response>" in text


# -- judge_items -------------------------------------------------------------------

def test_scores_are_clamped_and_summarized_with_a_pass_rate():
    judge = FakeJudge([{"score": 12, "justification": "a"}, {"score": 4, "justification": "b"},
                       {"score": -3, "justification": "c"}])
    items = [{"prompt": "p", "response": f"r{i}"} for i in range(3)]
    out = judge_items(items, judge, max_score=10, pass_threshold=7)
    assert [v["score"] for v in out["verdicts"]] == [10.0, 4.0, 0.0]
    assert [v["passed"] for v in out["verdicts"]] == [True, False, False]
    s = out["summary"]
    assert s["n_items"] == 3 and s["n_scored"] == 3 and s["n_errors"] == 0
    assert s["mean_score"] == pytest.approx(14 / 3, abs=1e-3)
    assert s["pass_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert s["provider"] == "fake"


def test_one_bad_item_is_recorded_and_the_rest_are_judged():
    judge = FakeJudge([ValueError("rate limited"), {"score": "high"}, {"score": 6}])
    out = judge_items([{"response": "a"}, {"response": "b"}, {"response": "c"}], judge)
    errors = [v["error"] for v in out["verdicts"]]
    assert errors[0] == "rate limited" and "not a number" in errors[1] and errors[2] is None
    assert out["summary"]["n_scored"] == 1 and out["summary"]["mean_score"] == 6


def test_a_judge_error_stops_the_whole_run():
    judge = FakeJudge([JudgeError("bad credentials")])
    with pytest.raises(JudgeError):
        judge_items([{"response": "a"}, {"response": "b"}], judge)


def test_an_empty_response_scores_zero_without_asking():
    judge = FakeJudge([])
    out = judge_items([{"prompt": "p", "response": "   "}], judge)
    assert out["verdicts"][0]["score"] == 0.0 and judge.calls == []


def test_max_items_caps_the_run():
    judge = FakeJudge([{"score": 5}] * 2)
    out = judge_items([{"response": "x"}] * 5, judge, max_items=2)
    assert out["summary"]["n_items"] == 2


# -- the Claude provider -------------------------------------------------------------

def test_anthropic_request_shape():
    sent = []
    judge = AnthropicJudge(client=_client(_message('{"score": 8, "justification": "ok"}'), sent))
    assert judge.model == DEFAULT_MODELS["anthropic"] == "claude-opus-5-5"
    assert judge.grade("sys", "user") == {"score": 8, "justification": "ok"}
    kwargs = sent[0]
    assert kwargs["model"] == "claude-opus-5-5"
    assert kwargs["system"] == "sys"
    assert kwargs["messages"] == [{"role": "user", "content": "user"}]
    assert kwargs["output_config"]["format"] == {"type": "json_schema", "schema": VERDICT_SCHEMA}
    assert kwargs["output_config"]["effort"] == "medium"
    # Refusal fallbacks are on by default, in the "default" form and its own beta header.
    assert kwargs["fallbacks"] == "default"
    assert kwargs["betas"] == ["server-side-fallback-2026-07-01"]


def test_anthropic_options_can_turn_off_fallbacks_and_effort():
    sent = []
    judge = AnthropicJudge("claude-haiku-4-5", effort=None, fallbacks=False,
                           client=_client(_message('{"score": 1, "justification": ""}'), sent))
    judge.grade("s", "u")
    assert "fallbacks" not in sent[0] and "betas" not in sent[0]
    assert "effort" not in sent[0]["output_config"]


def test_anthropic_refusal_and_truncation_are_item_errors():
    refused = AnthropicJudge(client=_client(_message(stop_reason="refusal", category="cyber"), []))
    with pytest.raises(ValueError, match="declined.*cyber"):
        refused.grade("s", "u")
    cut = AnthropicJudge(client=_client(_message(stop_reason="max_tokens"), []))
    with pytest.raises(ValueError, match="max_tokens"):
        cut.grade("s", "u")


# -- the Ollama provider -------------------------------------------------------------

class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_ollama_request_shape_and_answer():
    seen = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["body"] = json.loads(request.data)
        return _Resp(json.dumps({"message": {"content": '{"score": 3, "justification": "meh"}'}}).encode())

    judge = OllamaJudge(url="http://127.0.0.1:9", opener=opener)
    assert judge.grade("s", "u") == {"score": 3, "justification": "meh"}
    assert seen["url"] == "http://127.0.0.1:9/api/chat"
    assert seen["body"]["format"] == VERDICT_SCHEMA and seen["body"]["stream"] is False
    assert seen["body"]["model"] == DEFAULT_MODELS["ollama"]


def test_ollama_unreachable_is_a_judge_error():
    def opener(request, timeout):
        raise urllib.error.URLError("refused")

    with pytest.raises(JudgeError, match="cannot reach ollama"):
        OllamaJudge(opener=opener).grade("s", "u")


def test_make_judge_routes_and_refuses_unknown_providers():
    assert isinstance(make_judge("ollama", url="http://127.0.0.1:1"), OllamaJudge)
    assert isinstance(make_judge("anthropic", client=object()), AnthropicJudge)
    with pytest.raises(ValueError, match="unknown judge provider"):
        make_judge("openai")
