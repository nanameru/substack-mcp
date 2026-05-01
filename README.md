# substack-mcp

A Model Context Protocol (MCP) server for Substack. Lets Claude Code create
drafts, upload images, set cover thumbnails, schedule, and publish posts on
your Substack publication.

> Built on top of [`python-substack`](https://github.com/ma2za/python-substack).
> Uses Substack's internal API (no public posting API exists). Not affiliated
> with Substack Inc.

## Tools

**Required**

- `create_draft(title, content_markdown, subtitle?, audience?)` — Create a new draft from Markdown.
- `update_draft(post_id, title?, subtitle?, content_markdown?, audience?)` — Edit an existing draft.
- `upload_image(image_path)` — Upload a local file or remote URL to Substack's CDN, returning the URL.
- `publish_draft(post_id, send_email?, share_automatically?)` — Publish immediately. `send_email` toggles email delivery.

**Recommended**

- `schedule_draft(post_id, iso_datetime)` — Schedule a publish for a future date/time (ISO 8601).
- `unschedule_draft(post_id)` — Cancel a scheduled publish.
- `set_cover_image(post_id, image_url)` — Set the cover thumbnail (from `upload_image` URL).

**Utility**

- `list_drafts(limit?)` — List recent drafts.
- `get_draft(post_id)` — Get a draft's full body.
- `delete_draft(post_id)` — Permanent deletion.

## Setup

```bash
# 1. Install dependencies
uv pip install -e .

# 2. Make sure you're logged in to Substack in Chrome (or Brave/Edge) — that's it.

# 3. Save credentials — auto-detects your existing browser session
substack-mcp-setup

# 4. Register with Claude Code
claude mcp add substack-mcp --scope user -- /Users/$USER/substack/.venv/bin/substack-mcp
```

Restart Claude Code, then `/mcp` should show `substack-mcp` as `connected`.

### How auth works

By default `substack-mcp-setup` reads the `substack.sid` cookie directly from
your existing Chrome session via [pycookiecheat](https://pypi.org/project/pycookiecheat/).
Substack can't tell anything was automated because **nothing was**: it's the
same session you're already using.

macOS will prompt once for Keychain access ("Chrome Safe Storage"). Click
"Always Allow" so it doesn't ask again next time.

Supports: Chrome, Brave, Edge, Chromium, Vivaldi, Opera.

### Fallback modes

```bash
# Specific browser
substack-mcp-setup --from-browser brave

# Playwright-based (often blocked by Substack — use --chrome instead)
substack-mcp-setup --browser

# Manual paste from DevTools
substack-mcp-setup --manual
```

Tokens are stored at `~/Library/Application Support/substack-mcp/config.json`
with `0600` permissions.

## Security

The `substack.sid` cookie is **equivalent to a password** — anyone with it has
full account access (publish posts, edit billing, etc.). Treat it as such.

### Where the token lives

- macOS: `~/Library/Application Support/substack-mcp/config.json` (mode `0600`)
- Linux: `~/.config/substack-mcp/config.json` (mode `0600`)
- Or via env vars: `SUBSTACK_PUBLICATION_URL` + `SUBSTACK_SESSION_TOKEN` (env
  vars are inherited by child processes — be aware when spawning subprocesses)

The `.gitignore` excludes `config.json`; never commit it. The MCP also writes
a temporary cookie file via `tempfile.mkstemp` (mode `0600`) and deletes it in
a `finally` block — see `auth.py:write_cookie_file`.

### If a token leaks

1. **Sign out of all sessions**: Substack → Settings → Security → "Sign out of
   all sessions". This invalidates every existing `substack.sid` immediately.
2. Log back in to Substack in your browser.
3. Re-run `substack-mcp-setup` to capture the new cookie.

### Image upload safety

`upload_image` only accepts:
- HTTP(S) URLs, or
- Local files with image extensions (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`,
  `.heic`, `.heif`) that are **not** under sensitive system paths
  (`/etc`, `/System`, `~/.ssh`, `~/.aws`, `~/Library/Keychains`, etc.)

This guards against an assistant being tricked (via prompt injection in
fetched content) into uploading e.g. an SSH private key to Substack's CDN.

**Known limitation**: Markdown image syntax `![alt](path)` inside `create_draft`
is processed by `python-substack` and bypasses this validation. If you pass
untrusted Markdown, sanitize image paths first.

### Dependencies

Versions are pinned with `~=` (compatible release, no major bumps). Bumping
`python-substack` in particular should be reviewed — it talks to Substack's
private API and lives outside Substack's official surface.

## Notes

- `audience` accepts: `everyone` (default), `only_paid`, `founding`, `only_free`.
- Markdown image syntax `![alt](path/or/url)` auto-uploads local files when you call `create_draft`.
- The cover image (set via `set_cover_image`) is what appears on your publication
  homepage and in social shares. If you don't set one explicitly, Substack
  typically uses the first image in the body.
