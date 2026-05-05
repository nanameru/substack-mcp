"""Detect new replies on Substack chat threads, or post a reply.

Usage:
    python chat_check.py                                 # detect new replies, output JSON
    python chat_check.py reply <thread_id> "<body>"     # post a reply
    python chat_check.py reply <thread_id> "<body>" --parent <comment_id>
    python chat_check.py init                           # mark all current replies as seen (first-run setup)

Files:
    chat_state.json       — set of already-processed comment IDs
    chat_drafts.json      — pending drafts for long comments (Claude appends)
    chat_replied_log.json — log of auto-replies sent
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from substack_mcp.client import SubstackClient  # noqa: E402

PUB_ID = 8866032
SELF_USER_ID = 214533556
STATE_FILE = ROOT / "chat_state.json"
DRAFTS_FILE = ROOT / "chat_drafts.json"
REPLIED_LOG = ROOT / "chat_replied_log.json"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_threads(c):
    r = c._api._session.get(
        f"https://substack.com/api/v1/community/publications/{PUB_ID}/posts",
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("threads", [])


def list_replies(c, thread_id):
    r = c._api._session.get(
        f"https://substack.com/api/v1/community/posts/{thread_id}/comments"
        "?order=desc&initial=true",
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("replies", [])


def post_reply(c, thread_id, body, parent_id=None):
    r = c._api._session.post(
        f"https://substack.com/api/v1/community/posts/{thread_id}/comments",
        json={"body": body, "parent_id": parent_id},
        timeout=15,
    )
    if not (200 <= r.status_code < 300):
        raise RuntimeError(f"reply failed HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def collect_comments(client, mark_all_processed=False):
    state = load_json(STATE_FILE, {"processed_comment_ids": []})
    processed = set(state["processed_comment_ids"])

    new_comments = []
    threads = list_threads(client)

    for t in threads:
        cp = t.get("communityPost", {})
        thread_id = cp.get("id")
        if not thread_id:
            continue
        thread_body = (cp.get("body") or "")[:80]

        replies_data = list_replies(client, thread_id)
        for r in replies_data:
            comment = r.get("comment", {})
            cid = comment.get("id")
            if not cid or cid in processed:
                continue
            user_id = comment.get("user_id")
            if user_id == SELF_USER_ID:
                processed.add(cid)
                continue
            if mark_all_processed:
                processed.add(cid)
                continue
            new_comments.append({
                "comment_id": cid,
                "thread_id": thread_id,
                "thread_body": thread_body,
                "user_id": user_id,
                "user_name": r.get("user", {}).get("name", ""),
                "user_handle": r.get("user", {}).get("handle", ""),
                "body": comment.get("body", ""),
                "char_count": len(comment.get("body") or ""),
                "created_at": comment.get("created_at"),
                "parent_id": comment.get("parent_id"),
            })
            processed.add(cid)

    state["processed_comment_ids"] = sorted(processed)
    save_json(STATE_FILE, state)
    return new_comments


def cmd_detect():
    c = SubstackClient.from_env()
    new_comments = collect_comments(c, mark_all_processed=False)
    print(json.dumps(new_comments, ensure_ascii=False, indent=2))


def cmd_init():
    c = SubstackClient.from_env()
    collect_comments(c, mark_all_processed=True)
    state = load_json(STATE_FILE, {"processed_comment_ids": []})
    print(f"initialized: {len(state['processed_comment_ids'])} comment IDs marked as seen")


def cmd_reply(thread_id, body, parent_id=None):
    c = SubstackClient.from_env()
    result = post_reply(c, thread_id, body, parent_id)
    cid = None
    if isinstance(result, dict):
        cid = (result.get("comment") or {}).get("id")
    log = load_json(REPLIED_LOG, {"replies": []})
    log["replies"].append({
        "thread_id": thread_id,
        "body": body,
        "parent_id": parent_id,
        "response_comment_id": cid,
    })
    save_json(REPLIED_LOG, log)
    print(json.dumps({"ok": True, "response_comment_id": cid}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("detect")
    sub.add_parser("init")
    p_reply = sub.add_parser("reply")
    p_reply.add_argument("thread_id")
    p_reply.add_argument("body")
    p_reply.add_argument("--parent", default=None)
    args = parser.parse_args()

    if args.cmd in (None, "detect"):
        cmd_detect()
    elif args.cmd == "init":
        cmd_init()
    elif args.cmd == "reply":
        cmd_reply(args.thread_id, args.body, args.parent)


if __name__ == "__main__":
    main()
