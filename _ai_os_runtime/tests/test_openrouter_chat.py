from __future__ import annotations

import json
import unittest
from unittest import mock

from _ai_os_runtime.api import ai_os_api_server


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class OpenRouterChatTest(unittest.TestCase):
    def test_disables_reasoning_and_enforces_zero_data_retention(self) -> None:
        captured_request = None

        def fake_urlopen(request, timeout):
            nonlocal captured_request
            captured_request = request
            self.assertEqual(timeout, 240)
            return FakeResponse(
                {
                    "choices": [{"message": {"content": "Broker writes are locked."}}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 6},
                }
            )

        with (
            mock.patch.object(ai_os_api_server, "OPENROUTER_API_KEY", "test-key"),
            mock.patch.object(ai_os_api_server.urllib.request, "urlopen", fake_urlopen),
        ):
            content, status, usage = ai_os_api_server.openrouter_chat(
                "z-ai/glm-4.7-flash",
                "Explain the execution lock.",
            )

        self.assertIsNotNone(captured_request)
        request_payload = json.loads(captured_request.data.decode("utf-8"))
        self.assertEqual(
            request_payload["reasoning"],
            {"effort": "none", "exclude": True},
        )
        self.assertEqual(
            request_payload["provider"],
            {"zdr": True, "data_collection": "deny"},
        )
        self.assertEqual(content, "Broker writes are locked.")
        self.assertEqual(status, "called")
        self.assertEqual(usage["completion_tokens"], 6)


if __name__ == "__main__":
    unittest.main()
