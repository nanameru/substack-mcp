from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from substack_mcp.article_cli import publish_article


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def create_draft(self, **kwargs):
        self.calls.append(("create_draft", kwargs))
        return {"post_id": "123", "title": kwargs["title"], "edit_url": "https://example.test/edit"}

    def upload_image(self, image_path: str):
        self.calls.append(("upload_image", {"image_path": image_path}))
        return {"url": "https://cdn.example.test/cover.png"}

    def set_cover_image(self, **kwargs):
        self.calls.append(("set_cover_image", kwargs))
        return {"post_id": kwargs["post_id"], "cover_image": kwargs["image_url"]}

    def publish_draft(self, **kwargs):
        self.calls.append(("publish_draft", kwargs))
        return {"post_id": kwargs["post_id"], "public_url": "https://example.test/p/post"}


class PublishArticleTests(unittest.TestCase):
    def test_creates_draft_sets_cover_then_publishes_when_requested(self) -> None:
        client = FakeClient()
        with tempfile.TemporaryDirectory() as tmp:
            markdown = Path(tmp) / "article.md"
            markdown.write_text("# Hello\n\nBody", encoding="utf-8")

            result = publish_article(
                client,
                markdown_file=markdown,
                title="記事タイトル",
                subtitle="記事サブタイトル",
                cover_image="/tmp/cover.png",
                audience="everyone",
                publish=True,
                send_email=False,
            )

        self.assertEqual(
            [name for name, _ in client.calls],
            ["create_draft", "upload_image", "set_cover_image", "publish_draft"],
        )
        self.assertEqual(client.calls[0][1]["content_markdown"], "# Hello\n\nBody")
        self.assertEqual(client.calls[2][1]["post_id"], "123")
        self.assertEqual(client.calls[3][1]["send_email"], False)
        self.assertIn("published", result)

    def test_send_email_requires_publish(self) -> None:
        client = FakeClient()
        with tempfile.TemporaryDirectory() as tmp:
            markdown = Path(tmp) / "article.md"
            markdown.write_text("Body", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "--send-email requires --publish"):
                publish_article(
                    client,
                    markdown_file=markdown,
                    title="記事タイトル",
                    send_email=True,
                )

        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
