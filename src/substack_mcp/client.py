"""Substack API client wrapper."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from substack import Api as SubstackApi
from substack.post import Post

from .auth import Credentials, load_credentials, write_cookie_file

logger = logging.getLogger(__name__)

VALID_AUDIENCES = {"everyone", "only_paid", "founding", "only_free"}

ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".heif"}

# Paths that should never be readable for image upload — defense against
# accidentally exfiltrating sensitive files (e.g., SSH keys) if a malicious
# instruction tricks the assistant into calling `upload_image` with a
# system path.
_BLOCKED_PATH_PREFIXES = [
    Path("/etc"),
    Path("/private/etc"),
    Path("/private/var"),
    Path("/System"),
    Path("/usr"),
    Path.home() / ".ssh",
    Path.home() / ".aws",
    Path.home() / ".gnupg",
    Path.home() / ".kube",
    Path.home() / ".docker",
    Path.home() / "Library" / "Application Support" / "substack-mcp",
    Path.home() / "Library" / "Keychains",
    Path.home() / "Library" / "Cookies",
]


def _validate_image_path(image: str) -> None:
    if image.startswith(("http://", "https://")):
        return
    try:
        resolved = Path(image).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as e:
        raise ValueError(f"Cannot resolve image path: {image!r} ({e})") from e
    if resolved.suffix.lower() not in ALLOWED_IMAGE_EXTS:
        raise ValueError(
            f"Image must have one of these extensions: {sorted(ALLOWED_IMAGE_EXTS)}. "
            f"Got: {resolved.suffix!r}"
        )
    for blocked in _BLOCKED_PATH_PREFIXES:
        if resolved == blocked or resolved.is_relative_to(blocked):
            raise ValueError(
                f"Refusing to upload from sensitive path: {resolved}. "
                f"Move the image to a normal user directory (e.g., ~/Downloads, ~/Pictures) first."
            )


def _text_to_prosemirror_doc(text: str) -> dict:
    """Convert plain text (with line breaks) into a ProseMirror doc node.

    - Paragraphs are split by `\\n\\n` (a blank line).
    - Single `\\n` becomes a hardBreak inside the same paragraph.
    """
    paragraphs = text.split("\n\n")
    content: list[dict] = []
    for para in paragraphs:
        para_content: list[dict] = []
        lines = para.split("\n")
        for i, line in enumerate(lines):
            if line:
                para_content.append({"type": "text", "text": line})
            if i < len(lines) - 1:
                para_content.append({"type": "hardBreak"})
        if para_content:
            content.append({"type": "paragraph", "content": para_content})
    if not content:
        content = [{"type": "paragraph"}]
    return {
        "type": "doc",
        "attrs": {"schemaVersion": "v1", "title": None},
        "content": content,
    }


def _normalize_prosemirror(body_json: str) -> str:
    """Fix issues in python-substack's generated ProseMirror JSON.

    Bug 1: bullet/ordered list items emit text nodes shaped like
        {"content": "...", "marks": [...]}
    when ProseMirror requires
        {"type": "text", "text": "...", "marks": [...]}
    This walks the tree and rewrites any such nodes in place.
    """
    body = json.loads(body_json)
    _fix_node(body)
    return json.dumps(body)


def _fix_node(node: Any) -> None:
    if isinstance(node, list):
        for item in node:
            _fix_node(item)
        return
    if not isinstance(node, dict):
        return

    # Detect malformed text nodes: have "content" as string, no "type"
    if "type" not in node and isinstance(node.get("content"), str):
        text_value = node["content"]
        marks = node.get("marks")
        node.clear()
        node["type"] = "text"
        node["text"] = text_value
        if marks:
            node["marks"] = marks
        return

    # Recurse into children
    children = node.get("content")
    if children is not None:
        _fix_node(children)


class SubstackClient:
    def __init__(self, creds: Credentials):
        self.creds = creds
        cookie_path = write_cookie_file(creds.session_token)
        try:
            self._api = SubstackApi(
                cookies_path=str(cookie_path),
                publication_url=creds.publication_url,
            )
        finally:
            cookie_path.unlink(missing_ok=True)
        self._user_id: Optional[int] = None

    @classmethod
    def from_env(cls) -> "SubstackClient":
        creds = load_credentials()
        if creds is None:
            raise RuntimeError(
                "No Substack credentials found. Run `substack-mcp-setup` first, "
                "or set SUBSTACK_PUBLICATION_URL and SUBSTACK_SESSION_TOKEN."
            )
        return cls(creds)

    @property
    def user_id(self) -> int:
        if self._user_id is None:
            self._user_id = int(self._api.get_user_id())
        return self._user_id

    @property
    def publication_url(self) -> str:
        return self.creds.publication_url.rstrip("/")

    def create_draft(
        self,
        title: str,
        content_markdown: str,
        subtitle: str = "",
        audience: str = "everyone",
    ) -> dict:
        if audience not in VALID_AUDIENCES:
            raise ValueError(
                f"audience must be one of {sorted(VALID_AUDIENCES)}, got {audience!r}"
            )
        post = Post(
            title=title,
            subtitle=subtitle,
            user_id=self.user_id,
            audience=audience,
        )
        post.from_markdown(content_markdown, api=self._api)
        draft = post.get_draft()
        draft["draft_body"] = _normalize_prosemirror(draft["draft_body"])
        result = self._api.post_draft(draft)
        return self._summarize_draft(result)

    def update_draft(
        self,
        post_id: str,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        content_markdown: Optional[str] = None,
        audience: Optional[str] = None,
    ) -> dict:
        update: dict[str, Any] = {}
        if title is not None:
            update["draft_title"] = title
        if subtitle is not None:
            update["draft_subtitle"] = subtitle
        if audience is not None:
            if audience not in VALID_AUDIENCES:
                raise ValueError(
                    f"audience must be one of {sorted(VALID_AUDIENCES)}, got {audience!r}"
                )
            update["audience"] = audience
        if content_markdown is not None:
            tmp = Post(
                title=title or "",
                subtitle=subtitle or "",
                user_id=self.user_id,
                audience=audience or "everyone",
            )
            tmp.from_markdown(content_markdown, api=self._api)
            update["draft_body"] = _normalize_prosemirror(tmp.get_draft()["draft_body"])
        if not update:
            raise ValueError("Provide at least one of: title, subtitle, content_markdown, audience")
        result = self._api.put_draft(post_id, **update)
        return self._summarize_draft(result)

    def upload_image(self, image: str) -> dict:
        _validate_image_path(image)
        result = self._api.get_image(image)
        return {
            "url": result.get("url"),
            "id": result.get("id"),
            "image_id": result.get("imageId"),
            "width": result.get("imageWidth"),
            "height": result.get("imageHeight"),
            "raw": result,
        }

    def set_cover_image(self, post_id: str, image_url: str) -> dict:
        result = self._api.put_draft(post_id, cover_image=image_url)
        return self._summarize_draft(result)

    def publish_draft(
        self,
        post_id: str,
        send_email: bool = True,
        share_automatically: bool = False,
    ) -> dict:
        result = self._api.publish_draft(
            post_id,
            send=send_email,
            share_automatically=share_automatically,
        )
        slug = result.get("slug") or result.get("draft_slug") or ""
        public_url = f"{self.publication_url}/p/{slug}" if slug else None
        return {
            "post_id": str(result.get("id", post_id)),
            "title": result.get("title") or result.get("draft_title"),
            "public_url": public_url,
            "post_date": result.get("post_date"),
            "send_email": send_email,
        }

    def schedule_draft(self, post_id: str, iso_datetime: str) -> dict:
        try:
            dt = datetime.fromisoformat(iso_datetime)
        except ValueError as e:
            raise ValueError(
                f"iso_datetime must be ISO 8601 format (e.g., 2026-05-15T09:00:00+09:00). Got: {iso_datetime!r}"
            ) from e
        result = self._api.schedule_draft(post_id, dt)
        return {
            "post_id": post_id,
            "scheduled_for": dt.isoformat(),
            "raw": result,
        }

    def unschedule_draft(self, post_id: str) -> dict:
        result = self._api.unschedule_draft(post_id)
        return {"post_id": post_id, "raw": result}

    def list_drafts(self, limit: int = 10) -> list[dict]:
        if limit < 1 or limit > 50:
            raise ValueError("limit must be between 1 and 50")
        raw = self._api.get_drafts(filter="draft", limit=limit, offset=0) or []
        return [self._summarize_draft(d) for d in raw]

    def get_draft(self, post_id: str) -> dict:
        result = self._api.get_draft(post_id)
        return self._summarize_draft(result, include_body=True)

    def delete_draft(self, post_id: str) -> dict:
        self._api.delete_draft(post_id)
        return {"post_id": post_id, "deleted": True}

    def post_note(self, text: str) -> dict:
        """Post a Note (Substack's short-form, X-like post) to the public feed.

        Notes are not Posts: they don't trigger email delivery, don't appear on
        the publication's article archive, and have no title/subtitle. They show
        up in the Notes feed across Substack.

        Args:
            text: Plain text body. Use \\n\\n to separate paragraphs and \\n
                for soft line breaks.

        Returns:
            {note_id, url, raw}
        """
        if not text or not isinstance(text, str):
            raise ValueError("text must be a non-empty string")
        if len(text) > 4000:
            raise ValueError("text is too long for a Note (>4000 chars)")

        body_json = _text_to_prosemirror_doc(text)
        payload = {
            "bodyJson": body_json,
            "tabId": "for-you",
            "surface": "feed",
            "replyMinimumRole": "everyone",
        }

        response = self._api._session.post(
            "https://substack.com/api/v1/comment/feed",
            json=payload,
            timeout=15,
        )
        if not (200 <= response.status_code < 300):
            raise RuntimeError(
                f"Note post failed: HTTP {response.status_code} {response.text[:500]}"
            )
        data = response.json()
        note_id = data.get("id") or data.get("note_id")
        # Public Notes URL: https://substack.com/@<handle>/note/c-<id>
        # We don't always have the handle; fall back to the user_id form.
        url = None
        if note_id is not None:
            url = f"https://substack.com/note/c-{note_id}"
        return {
            "note_id": str(note_id) if note_id is not None else None,
            "url": url,
            "raw": data,
        }

    def _summarize_draft(self, draft: dict, include_body: bool = False) -> dict:
        if not isinstance(draft, dict):
            return {"raw": draft}
        post_id = draft.get("id")
        out = {
            "post_id": str(post_id) if post_id is not None else None,
            "title": draft.get("draft_title") or draft.get("title"),
            "subtitle": draft.get("draft_subtitle") or draft.get("subtitle"),
            "audience": draft.get("audience"),
            "post_date": draft.get("post_date"),
            "is_published": draft.get("post_date") is not None,
            "cover_image": draft.get("cover_image"),
            "edit_url": (
                f"{self.publication_url}/publish/post/{post_id}"
                if post_id
                else None
            ),
        }
        if include_body:
            out["draft_body"] = draft.get("draft_body") or draft.get("body")
        return out
