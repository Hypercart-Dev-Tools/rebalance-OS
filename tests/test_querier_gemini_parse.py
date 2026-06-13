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

from rebalance.ingest.querier import _synthesize_gemini


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


if __name__ == "__main__":
    unittest.main()
