"""_synthesize_gemini must not crash on valid-but-textless Gemini responses.

Regression: the parser indexed payload['candidates'][0]['content']['parts'][0]
['text'] with bare subscripts. A MAX_TOKENS-truncated or SAFETY-blocked
response is valid JSON but carries no 'parts' (or no 'candidates'), so this
raised KeyError/IndexError — which ask() then mislabelled as a hard Gemini
failure and logged as "Gemini synthesis failed". The parser must instead raise
a clear RuntimeError (carrying finishReason/blockReason), and should return any
partial text a truncated response did manage to produce.
"""

import json
import unittest
from unittest.mock import patch

from rebalance.ingest.querier import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_GEMINI_MODEL,
    _synthesize_gemini,
    _synthesize_with_fallback,
)


class _FakeResp:
    def __init__(self, payload: dict) -> None:
        self._b = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._b

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *_a) -> bool:
        return False


def _call(payload: dict) -> str:
    with patch("urllib.request.urlopen", return_value=_FakeResp(payload)):
        return _synthesize_gemini("prompt", api_key="k")


class TestSynthesizeGeminiParse(unittest.TestCase):
    def test_happy_path_returns_text(self) -> None:
        out = _call({"candidates": [{"content": {"parts": [{"text": "hello "}]}}]})
        self.assertEqual(out, "hello")

    def test_max_tokens_no_parts_raises_runtimeerror(self) -> None:
        # Before the fix: KeyError('parts'). After: a clear RuntimeError.
        with self.assertRaises(RuntimeError) as ctx:
            _call({"candidates": [{"finishReason": "MAX_TOKENS", "content": {"role": "model"}}]})
        self.assertIn("MAX_TOKENS", str(ctx.exception))

    def test_safety_block_no_candidates_raises_runtimeerror(self) -> None:
        # Before the fix: KeyError('candidates'). After: a clear RuntimeError.
        with self.assertRaises(RuntimeError) as ctx:
            _call({"promptFeedback": {"blockReason": "SAFETY"}})
        self.assertIn("SAFETY", str(ctx.exception))

    def test_empty_parts_list_raises_runtimeerror(self) -> None:
        # Before the fix: IndexError. After: a clear RuntimeError.
        with self.assertRaises(RuntimeError):
            _call({"candidates": [{"content": {"parts": []}}]})

    def test_truncated_but_partial_text_is_returned(self) -> None:
        # A MAX_TOKENS response that still produced some text should not be lost.
        out = _call({
            "candidates": [
                {"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "partial answer"}]}}
            ]
        })
        self.assertEqual(out, "partial answer")

    def test_no_keyerror_or_indexerror_leaks(self) -> None:
        # The whole point: the bad shapes raise RuntimeError, never the raw
        # KeyError/IndexError that ask() would mislabel.
        for payload in (
            {},
            {"candidates": []},
            {"candidates": [{"finishReason": "SAFETY"}]},
            {"candidates": [{"content": {}}]},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(RuntimeError):
                    _call(payload)


class TestSynthesizeWithFallback(unittest.TestCase):
    """The Gemini -> Qwen ladder extracted from ask()."""

    def test_gemini_success(self) -> None:
        with patch("rebalance.ingest.config.get_gemini_api_key", return_value="k"), \
                patch(
                    "rebalance.ingest.querier._synthesize_gemini",
                    return_value="gemini answer",
                ) as g, \
                patch("rebalance.ingest.querier._synthesize") as q:
            text, model = _synthesize_with_fallback("prompt")
        self.assertEqual(text, "gemini answer")
        self.assertEqual(model, DEFAULT_GEMINI_MODEL)
        g.assert_called_once()
        q.assert_not_called()

    def test_gemini_raises_falls_back_to_qwen(self) -> None:
        with patch("rebalance.ingest.config.get_gemini_api_key", return_value="k"), \
                patch(
                    "rebalance.ingest.querier._synthesize_gemini",
                    side_effect=RuntimeError("boom"),
                ), \
                patch(
                    "rebalance.ingest.querier._synthesize",
                    return_value="qwen answer",
                ) as q, \
                self.assertLogs("rebalance.ingest.querier", level="WARNING") as logs:
            text, model = _synthesize_with_fallback("prompt")
        self.assertEqual(text, "qwen answer")
        self.assertEqual(model, f"{DEFAULT_CHAT_MODEL} (gemini-fallback)")
        q.assert_called_once()
        self.assertTrue(
            any("Gemini synthesis failed" in m for m in logs.output),
            logs.output,
        )

    def test_both_fail_returns_sentinel_and_dual_failure_log(self) -> None:
        with patch("rebalance.ingest.config.get_gemini_api_key", return_value="k"), \
                patch(
                    "rebalance.ingest.querier._synthesize_gemini",
                    side_effect=RuntimeError("gemini down"),
                ), \
                patch(
                    "rebalance.ingest.querier._synthesize",
                    side_effect=RuntimeError("qwen down"),
                ), \
                self.assertLogs("rebalance.ingest.querier", level="WARNING") as logs:
            text, model = _synthesize_with_fallback("prompt")
        self.assertEqual(text, "[LLM synthesis failed: qwen down]")
        self.assertEqual(model, f"{DEFAULT_CHAT_MODEL} (failed)")
        self.assertTrue(
            any(
                "Qwen fallback also failed after Gemini failure" in m
                for m in logs.output
            ),
            logs.output,
        )

    def test_no_gemini_key_uses_qwen_directly(self) -> None:
        with patch("rebalance.ingest.config.get_gemini_api_key", return_value=""), \
                patch(
                    "rebalance.ingest.querier._synthesize_gemini",
                ) as g, \
                patch(
                    "rebalance.ingest.querier._synthesize",
                    return_value="qwen answer",
                ):
            text, model = _synthesize_with_fallback("prompt")
        self.assertEqual(text, "qwen answer")
        self.assertEqual(model, DEFAULT_CHAT_MODEL)
        g.assert_not_called()

    def test_no_gemini_key_qwen_fails_returns_local_sentinel(self) -> None:
        with patch("rebalance.ingest.config.get_gemini_api_key", return_value=""), \
                patch(
                    "rebalance.ingest.querier._synthesize",
                    side_effect=RuntimeError("qwen down"),
                ):
            text, model = _synthesize_with_fallback("prompt")
        self.assertEqual(text, "[Local LLM synthesis failed: qwen down]")
        self.assertEqual(model, f"{DEFAULT_CHAT_MODEL} (failed)")


class TestThinkingBudget(unittest.TestCase):
    """thinking_budget=0 must disable Gemini reasoning so a long structured list
    is not truncated to a couple of items at finishReason=MAX_TOKENS."""

    def _capture_body(self, **kwargs: object) -> dict:
        captured: dict = {}

        def fake_urlopen(req, *_a, **_k):
            captured["body"] = json.loads(req.data.decode())
            return _FakeResp({"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            _synthesize_gemini("prompt", api_key="k", **kwargs)
        return captured["body"]

    def test_thinking_config_set_when_budget_given(self) -> None:
        body = self._capture_body(thinking_budget=0)
        self.assertEqual(
            body["generationConfig"]["thinkingConfig"]["thinkingBudget"], 0
        )

    def test_no_thinking_config_by_default(self) -> None:
        body = self._capture_body()
        self.assertNotIn("thinkingConfig", body["generationConfig"])

    def test_fallback_forwards_thinking_budget_to_gemini(self) -> None:
        captured: dict = {}

        def fake_urlopen(req, *_a, **_k):
            captured["body"] = json.loads(req.data.decode())
            return _FakeResp({"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

        with patch("rebalance.ingest.config.get_gemini_api_key", return_value="k"), \
                patch("urllib.request.urlopen", side_effect=fake_urlopen):
            _text, model = _synthesize_with_fallback("p", thinking_budget=0)
        self.assertEqual(
            captured["body"]["generationConfig"]["thinkingConfig"]["thinkingBudget"], 0
        )
        self.assertEqual(model, DEFAULT_GEMINI_MODEL)


if __name__ == "__main__":
    unittest.main()
