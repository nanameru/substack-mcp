"""Post a Substack Note with attached image(s).

Three-step flow:
  1. Upload image to Substack CDN: POST {publication_url}/image
  2. Create attachment record:    POST /api/v1/comment/attachment
  3. Post Note with attachmentIds: POST /api/v1/comment/feed

Usage:
    python post_note_with_image.py <text_file> <image1.png> [<image2.png> ...]
    cat body.txt | python post_note_with_image.py --stdin <image1.png> [...]

Body file uses the same blank-line-as-paragraph rule as post_note.py.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from substack_mcp.client import SubstackClient, _text_to_prosemirror_doc  # noqa: E402


def create_attachment(client, image_url: str) -> str:
    r = client._api._session.post(
        "https://substack.com/api/v1/comment/attachment",
        json={"url": image_url, "type": "image"},
        timeout=15,
    )
    if not (200 <= r.status_code < 300):
        raise RuntimeError(f"attachment create failed HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    return data["id"]


def post_note_with_attachments(client, text: str, attachment_ids: list[str]) -> dict:
    body_json = _text_to_prosemirror_doc(text)
    payload = {
        "bodyJson": body_json,
        "tabId": "for-you",
        "surface": "feed",
        "replyMinimumRole": "everyone",
        "attachmentIds": attachment_ids,
    }
    r = client._api._session.post(
        "https://substack.com/api/v1/comment/feed",
        json=payload,
        timeout=20,
    )
    if not (200 <= r.status_code < 300):
        raise RuntimeError(f"note post failed HTTP {r.status_code}: {r.text[:500]}")
    return r.json()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("text_or_image", help="Body text file path, OR if --stdin used, first image path")
    p.add_argument("images", nargs="*")
    p.add_argument("--stdin", action="store_true", help="Read body text from stdin")
    args = p.parse_args()

    if args.stdin:
        text = sys.stdin.read().strip()
        image_paths = [args.text_or_image] + args.images
    else:
        text = Path(args.text_or_image).read_text(encoding="utf-8").strip()
        image_paths = args.images

    if not text:
        print("error: empty body text", file=sys.stderr)
        return 1
    if not image_paths:
        print("error: at least one image path required", file=sys.stderr)
        return 1

    client = SubstackClient.from_env()

    print(f"[1/3] uploading {len(image_paths)} image(s) to Substack CDN...", file=sys.stderr)
    image_urls = []
    for ip in image_paths:
        result = client.upload_image(ip)
        image_urls.append(result["url"])
        print(f"      {ip} -> {result['url']}", file=sys.stderr)

    print(f"[2/3] creating attachment records...", file=sys.stderr)
    attachment_ids = []
    for url in image_urls:
        aid = create_attachment(client, url)
        attachment_ids.append(aid)
        print(f"      {url[:60]}... -> {aid}", file=sys.stderr)

    print(f"[3/3] posting note...", file=sys.stderr)
    result = post_note_with_attachments(client, text, attachment_ids)
    note_id = result.get("id")
    print(f"\nposted note_id: {note_id}")
    print(f"url: https://substack.com/note/c-{note_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
