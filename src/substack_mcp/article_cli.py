"""CLI for creating Substack articles with optional cover images."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .constants import VALID_AUDIENCES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="substack-publish-article",
        description=(
            "Create a Substack article draft from Markdown, optionally upload a "
            "cover image, and publish only when --publish is supplied."
        ),
    )
    parser.add_argument("markdown_file", help="Path to the article Markdown file")
    parser.add_argument("--title", required=True, help="Article title")
    parser.add_argument("--subtitle", default="", help="Article subtitle")
    parser.add_argument(
        "--cover-image",
        help="Local image path or public URL to upload and set as the cover image",
    )
    parser.add_argument(
        "--audience",
        default="everyone",
        choices=sorted(VALID_AUDIENCES),
        help="Substack audience setting",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish immediately after creating the draft and setting the cover",
    )
    parser.add_argument(
        "--send-email",
        action="store_true",
        help="Send email to subscribers. Requires --publish.",
    )
    parser.add_argument(
        "--share-automatically",
        action="store_true",
        help="Ask Substack to auto-share after publish. Requires --publish.",
    )
    return parser


def publish_article(
    client: Any,
    *,
    markdown_file: Path,
    title: str,
    subtitle: str = "",
    cover_image: str | None = None,
    audience: str = "everyone",
    publish: bool = False,
    send_email: bool = False,
    share_automatically: bool = False,
) -> dict[str, Any]:
    if send_email and not publish:
        raise ValueError("--send-email requires --publish")
    if share_automatically and not publish:
        raise ValueError("--share-automatically requires --publish")
    if audience not in VALID_AUDIENCES:
        raise ValueError(f"audience must be one of {sorted(VALID_AUDIENCES)}")
    if not markdown_file.exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown_file}")

    content = markdown_file.read_text(encoding="utf-8")
    draft = client.create_draft(
        title=title,
        content_markdown=content,
        subtitle=subtitle,
        audience=audience,
    )

    result: dict[str, Any] = {"draft": draft}
    post_id = draft.get("post_id")
    if cover_image:
        if not post_id:
            raise RuntimeError("Cannot set cover image because draft has no post_id")
        upload = client.upload_image(cover_image)
        cover_url = upload.get("url")
        if not cover_url:
            raise RuntimeError(f"Image upload did not return a url: {upload!r}")
        result["image"] = upload
        result["cover"] = client.set_cover_image(post_id=post_id, image_url=cover_url)

    if publish:
        if not post_id:
            raise RuntimeError("Cannot publish because draft has no post_id")
        result["published"] = client.publish_draft(
            post_id=post_id,
            send_email=send_email,
            share_automatically=share_automatically,
        )

    return result


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        from .client import SubstackClient

        result = publish_article(
            SubstackClient.from_env(),
            markdown_file=Path(args.markdown_file),
            title=args.title,
            subtitle=args.subtitle,
            cover_image=args.cover_image,
            audience=args.audience,
            publish=args.publish,
            send_email=args.send_email,
            share_automatically=args.share_automatically,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
