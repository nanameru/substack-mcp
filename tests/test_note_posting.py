"""Regression tests for safe Substack Note requests."""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from substack_mcp.client import (
    SubstackClient,
    SubstackHTTPError,
    SubstackOperationError,
    _text_to_prosemirror_doc,
)
from substack_mcp.cloud_api import _public_error_response


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: dict | Exception,
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self) -> dict:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse | Exception):
        self.response = response
        self.calls: list[dict] = []

    def post(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def make_client(response: FakeResponse | Exception) -> tuple[SubstackClient, FakeSession]:
    session = FakeSession(response)
    client = object.__new__(SubstackClient)
    client.creds = SimpleNamespace(publication_url="https://example.substack.com")
    client._api = SimpleNamespace(_session=session)
    client._user_id = None
    return client, session


class NotePayloadTests(unittest.TestCase):
    def test_document_omits_null_title_attribute(self) -> None:
        document = _text_to_prosemirror_doc("First paragraph\n\nSecond paragraph")

        self.assertEqual(document["attrs"], {"schemaVersion": "v1"})
        self.assertNotIn("title", document["attrs"])

    def test_post_note_sends_expected_payload(self) -> None:
        client, session = make_client(FakeResponse(200, {"id": 123}))

        result = client.post_note("Practical AI tip")

        self.assertEqual(result["note_id"], "123")
        self.assertEqual(len(session.calls), 1)
        call = session.calls[0]
        self.assertEqual(call["url"], "https://substack.com/api/v1/comment/feed/")
        self.assertEqual(call["timeout"], 15)
        self.assertEqual(
            call["json"],
            {
                "bodyJson": {
                    "type": "doc",
                    "attrs": {"schemaVersion": "v1"},
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "Practical AI tip"}]}
                    ],
                },
                "tabId": "for-you",
                "surface": "feed",
                "replyMinimumRole": "everyone",
            },
        )


class NoteErrorTests(unittest.TestCase):
    def test_request_exception_reports_phase_without_exception_message(self) -> None:
        private_message = "transport failure containing private submitted body"
        client, _ = make_client(RuntimeError(private_message))

        with self.assertRaises(SubstackOperationError) as raised:
            client.post_note("private submitted body")

        public = raised.exception.public_message()
        self.assertIn("phase=request", public)
        self.assertIn("exception=RuntimeError", public)
        self.assertNotIn(private_message, public)
        self.assertNotIn("private submitted body", public)

    def test_success_response_json_exception_reports_parse_phase(self) -> None:
        private_message = "parser failure containing response payload"
        client, _ = make_client(FakeResponse(200, RuntimeError(private_message)))

        with self.assertRaises(SubstackOperationError) as raised:
            client.post_note("body must not appear")

        public = raised.exception.public_message()
        self.assertIn("phase=response_json", public)
        self.assertIn("exception=RuntimeError", public)
        self.assertIn("status=200", public)
        self.assertNotIn(private_message, public)
        self.assertNotIn("body must not appear", public)

    def test_upstream_failure_exposes_only_safe_diagnostics(self) -> None:
        private_message = "invalid cookie substack.sid=do-not-leak and submitted body"
        response = FakeResponse(
            403,
            {"error_code": "write_not_authorized", "message": private_message},
            {"x-request-id": "req_123-safe"},
        )
        client, _ = make_client(response)

        with self.assertRaises(SubstackHTTPError) as raised:
            client.post_note("private submitted body")

        error = raised.exception
        self.assertEqual(error.status_code, 403)
        self.assertEqual(error.error_code, "write_not_authorized")
        self.assertEqual(error.request_id, "req_123-safe")
        public = error.public_message()
        self.assertIn("status=403", public)
        self.assertIn("code=write_not_authorized", public)
        self.assertNotIn("substack.sid", public)
        self.assertNotIn("private", public)
        self.assertNotIn(private_message, json.dumps(_public_error_response(error)))

    def test_untrusted_error_fields_are_discarded(self) -> None:
        response = FakeResponse(
            400,
            {"error_code": "bad value with spaces and secret=123"},
            {"x-request-id": "unsafe request id with spaces"},
        )
        client, _ = make_client(response)

        with self.assertRaises(SubstackHTTPError) as raised:
            client.post_note("body must not appear")

        self.assertIsNone(raised.exception.error_code)
        self.assertIsNone(raised.exception.request_id)
        self.assertNotIn("body must not appear", raised.exception.public_message())

    def test_unknown_exception_response_remains_generic(self) -> None:
        status, payload = _public_error_response(RuntimeError("secret internal failure"))

        self.assertEqual(status, 502)
        self.assertEqual(payload, {"error": "Substack operation failed: RuntimeError"})
        self.assertNotIn("secret internal failure", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
