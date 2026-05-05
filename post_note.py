"""Quick CLI to post a Substack Note.

Usage:
    python post_note.py "text to post"
    python post_note.py --stdin   # read text from stdin
"""

from __future__ import annotations

import argparse
import json
import sys

from substack_mcp.client import SubstackClient


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="?", default=None)
    parser.add_argument("--stdin", action="store_true")
    args = parser.parse_args()

    if args.stdin:
        text = sys.stdin.read()
    else:
        text = args.text

    if not text or not text.strip():
        print("error: empty text", file=sys.stderr)
        return 1

    client = SubstackClient.from_env()
    result = client.post_note(text.strip())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
