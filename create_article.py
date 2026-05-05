"""Create a Substack article draft from a markdown file.

Usage:
    python create_article.py <markdown_file> <title> [--subtitle "..."] [--publish] [--audience everyone]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from substack_mcp.client import SubstackClient


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("markdown_file")
    parser.add_argument("title")
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--publish", action="store_true", help="Publish immediately after create")
    parser.add_argument("--send-email", action="store_true", help="Email subscribers (only with --publish)")
    parser.add_argument("--audience", default="everyone",
                        choices=["everyone", "only_paid", "founding", "only_free"])
    args = parser.parse_args()

    md_path = Path(args.markdown_file)
    if not md_path.exists():
        print(f"error: file not found: {md_path}", file=sys.stderr)
        return 1

    content = md_path.read_text(encoding="utf-8")

    client = SubstackClient.from_env()
    draft = client.create_draft(
        title=args.title,
        content_markdown=content,
        subtitle=args.subtitle,
        audience=args.audience,
    )
    print(json.dumps(draft, ensure_ascii=False, indent=2))

    if args.publish and draft.get("post_id"):
        published = client.publish_draft(
            post_id=draft["post_id"],
            send_email=args.send_email,
            share_automatically=False,
        )
        print(json.dumps(published, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
