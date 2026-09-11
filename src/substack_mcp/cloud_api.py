"""Private HTTP bridge used by the Cloudflare Container deployment."""

from __future__ import annotations

import json
import logging
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .client import SubstackClient

logger = logging.getLogger("substack-mcp-cloud-api")
MAX_BODY_BYTES = 8 * 1024 * 1024
_client: SubstackClient | None = None
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")


def _get_client() -> SubstackClient:
    global _client
    if _client is None:
        _client = SubstackClient.from_env()
    return _client


def _validate_cloud_markdown(markdown: str) -> None:
    """Cloud containers must never read local files referenced by Markdown."""
    for source in MARKDOWN_IMAGE_RE.findall(markdown):
        if urlparse(source).scheme != "https":
            raise ValueError("Markdown images in cloud mode must use public HTTPS URLs")


def _validate_https_url(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a public HTTPS URL")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower() == "localhost":
        raise ValueError(f"{field} must be a public HTTPS URL")
    return value


def _invoke(tool: str, arguments: dict[str, Any]) -> Any:
    client = _get_client()

    if tool == "create_draft":
        title = arguments.get("title")
        content = arguments.get("content_markdown")
        subtitle = arguments.get("subtitle", "")
        if not isinstance(title, str) or not title or len(title) > 280:
            raise ValueError("title must be a non-empty string of at most 280 characters")
        if not isinstance(content, str) or not content:
            raise ValueError("content_markdown must be non-empty")
        _validate_cloud_markdown(content)
        if not isinstance(subtitle, str) or len(subtitle) > 280:
            raise ValueError("subtitle must be at most 280 characters")
        return client.create_draft(
            title=title,
            content_markdown=content,
            subtitle=subtitle,
            audience=arguments.get("audience", "everyone"),
        )

    if tool == "update_draft":
        content = arguments.get("content_markdown")
        if content is not None:
            if not isinstance(content, str) or not content:
                raise ValueError("content_markdown must be a non-empty string")
            _validate_cloud_markdown(content)
        return client.update_draft(**arguments)
    if tool == "upload_image":
        image_url = _validate_https_url(arguments.get("image_url"), "image_url")
        result = client.upload_image(image_url)
        return {key: result.get(key) for key in ("url", "id", "image_id", "width", "height")}
    if tool == "set_cover_image":
        return client.set_cover_image(**arguments)
    if tool == "publish_draft":
        return client.publish_draft(**arguments)
    if tool == "schedule_draft":
        result = client.schedule_draft(**arguments)
        return {"post_id": result["post_id"], "scheduled_for": result["scheduled_for"]}
    if tool == "unschedule_draft":
        client.unschedule_draft(**arguments)
        return {"post_id": arguments["post_id"]}
    if tool == "list_drafts":
        return client.list_drafts(**arguments)
    if tool == "get_draft":
        return client.get_draft(**arguments)
    if tool == "delete_draft":
        return client.delete_draft(**arguments)
    if tool == "post_note":
        result = client.post_note(**arguments)
        return {"note_id": result.get("note_id"), "url": result.get("url")}
    raise ValueError(f"Unknown tool: {tool}")


class Handler(BaseHTTPRequestHandler):
    server_version = "substack-mcp-cloud-api"

    def _json(self, status: int, payload: Any) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/ping":
            self._json(200, {"ok": True})
            return
        self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/invoke":
            self._json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > MAX_BODY_BYTES:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(length))
            tool = payload.get("tool")
            arguments = payload.get("arguments", {})
            if not isinstance(tool, str) or not isinstance(arguments, dict):
                raise ValueError("Request must contain tool and arguments")
            self._json(200, {"result": _invoke(tool, arguments)})
        except (KeyError, TypeError, ValueError) as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:  # keep credentials and tracebacks out of responses
            logger.exception("Substack operation failed")
            self._json(502, {"error": f"Substack operation failed: {type(exc).__name__}"})

    def log_message(self, format: str, *args: Any) -> None:
        logger.info(format, *args)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()


if __name__ == "__main__":
    main()
