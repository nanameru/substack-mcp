"""MCP server exposing Substack publishing tools."""

from __future__ import annotations

import logging
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .client import SubstackClient

logger = logging.getLogger("substack-mcp")

mcp = FastMCP("substack-mcp")
_client: Optional[SubstackClient] = None


def _get_client() -> SubstackClient:
    global _client
    if _client is None:
        _client = SubstackClient.from_env()
    return _client


@mcp.tool()
def create_draft(
    title: str,
    content_markdown: str,
    subtitle: str = "",
    audience: str = "everyone",
) -> dict:
    """Create a new Substack draft post from Markdown.

    Args:
        title: Post title (max 280 chars).
        content_markdown: Body in Markdown. Supports headings, bold/italic, links,
            bullet lists, blockquotes, code blocks, and images (![alt](url) - local
            paths are auto-uploaded to Substack CDN).
        subtitle: Optional subtitle (max 280 chars).
        audience: Who can read it: 'everyone' (default), 'only_paid', 'founding',
            or 'only_free'.

    Returns:
        Summary including post_id, title, edit_url.
    """
    if not title or not isinstance(title, str):
        raise ValueError("title must be a non-empty string")
    if len(title) > 280:
        raise ValueError("title must be 280 characters or less")
    if subtitle and len(subtitle) > 280:
        raise ValueError("subtitle must be 280 characters or less")
    if not content_markdown:
        raise ValueError("content_markdown must be non-empty")
    return _get_client().create_draft(
        title=title,
        content_markdown=content_markdown,
        subtitle=subtitle,
        audience=audience,
    )


@mcp.tool()
def update_draft(
    post_id: str,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    content_markdown: Optional[str] = None,
    audience: Optional[str] = None,
) -> dict:
    """Update an existing draft. Provide only the fields you want to change.

    Args:
        post_id: Draft ID returned by create_draft or list_drafts.
        title: New title (optional).
        subtitle: New subtitle (optional).
        content_markdown: New body in Markdown (optional, replaces full body).
        audience: New audience setting (optional).

    Returns:
        Updated draft summary.
    """
    return _get_client().update_draft(
        post_id=post_id,
        title=title,
        subtitle=subtitle,
        content_markdown=content_markdown,
        audience=audience,
    )


@mcp.tool()
def upload_image(image_path: str) -> dict:
    """Upload an image to Substack's CDN and return its public URL.

    Args:
        image_path: Local file path (e.g., /Users/foo/cover.png) or remote URL.

    Returns:
        {url, id, width, height} — pass `url` to set_cover_image or embed in
        Markdown as ![alt](url).
    """
    if not image_path:
        raise ValueError("image_path must be non-empty")
    return _get_client().upload_image(image_path)


@mcp.tool()
def set_cover_image(post_id: str, image_url: str) -> dict:
    """Set the cover (thumbnail) image for a draft.

    The cover image is shown on the publication homepage, in social shares,
    and as the email header. Use upload_image first to get a CDN URL.

    Args:
        post_id: Draft ID.
        image_url: Substack CDN URL from upload_image, or any public image URL.

    Returns:
        Updated draft summary.
    """
    return _get_client().set_cover_image(post_id=post_id, image_url=image_url)


@mcp.tool()
def publish_draft(
    post_id: str,
    send_email: bool = True,
    share_automatically: bool = False,
) -> dict:
    """Publish a draft immediately.

    Args:
        post_id: Draft ID.
        send_email: If True (default), send the post as an email to subscribers.
            If False, publish to web only without emailing.
        share_automatically: If True, auto-share to Substack social channels.

    Returns:
        {post_id, title, public_url, post_date, send_email}
    """
    return _get_client().publish_draft(
        post_id=post_id,
        send_email=send_email,
        share_automatically=share_automatically,
    )


@mcp.tool()
def schedule_draft(post_id: str, iso_datetime: str) -> dict:
    """Schedule a draft to publish at a future datetime.

    Args:
        post_id: Draft ID.
        iso_datetime: ISO 8601 datetime, e.g., '2026-05-15T09:00:00+09:00' for
            JST or '2026-05-15T00:00:00Z' for UTC.

    Returns:
        {post_id, scheduled_for}
    """
    return _get_client().schedule_draft(post_id=post_id, iso_datetime=iso_datetime)


@mcp.tool()
def unschedule_draft(post_id: str) -> dict:
    """Cancel a scheduled publish, keeping the post as a draft.

    Args:
        post_id: Draft ID.

    Returns:
        {post_id}
    """
    return _get_client().unschedule_draft(post_id=post_id)


@mcp.tool()
def list_drafts(limit: int = 10) -> list[dict]:
    """List recent drafts (unpublished posts).

    Args:
        limit: Max number of drafts to return (1-50). Default 10.

    Returns:
        List of draft summaries with post_id, title, edit_url, etc.
    """
    return _get_client().list_drafts(limit=limit)


@mcp.tool()
def get_draft(post_id: str) -> dict:
    """Get full details of a specific draft, including the body content.

    Args:
        post_id: Draft ID.

    Returns:
        Full draft data including draft_body (ProseMirror JSON).
    """
    return _get_client().get_draft(post_id=post_id)


@mcp.tool()
def delete_draft(post_id: str) -> dict:
    """Permanently delete a draft. This cannot be undone.

    Args:
        post_id: Draft ID.

    Returns:
        {post_id, deleted: true}
    """
    return _get_client().delete_draft(post_id=post_id)


@mcp.tool()
def post_note(text: str) -> dict:
    """Post a Note (Substack's short-form, X/Threads-like post) to the public feed.

    Notes are different from Posts:
    - No title or subtitle.
    - No email delivery to subscribers.
    - Not added to the publication's article archive.
    - Visible in the Substack Notes feed (cross-publication discovery surface).

    Use Notes for:
    - Quick thoughts, links, restacks, questions to your audience
    - Daily presence between long-form posts
    - Networking with other Substackers (replies, mutual follows)

    Args:
        text: Plain text body. Use \\n\\n to separate paragraphs and \\n for
            soft line breaks. Max 4000 chars (Substack's practical Notes limit).

    Returns:
        {note_id, url, raw}
    """
    if not text:
        raise ValueError("text must be non-empty")
    return _get_client().post_note(text=text)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    mcp.run()


if __name__ == "__main__":
    main()
