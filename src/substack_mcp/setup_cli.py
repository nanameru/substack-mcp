"""Setup CLI for Substack MCP credentials.

Two modes:
  - Browser (default): launches Chromium, you log in, cookie is captured
    automatically.
  - Manual (--manual): enter publication URL and substack.sid token by hand.
"""

from __future__ import annotations

import argparse
import sys
from urllib.parse import urlparse

from substack import Api as SubstackApi

from .auth import (
    CONFIG_FILE,
    Credentials,
    load_credentials,
    save_credentials,
    write_cookie_file,
)


BANNER = """
============================================================
 Substack MCP — Setup Wizard
============================================================
This wizard saves your Substack credentials to:
  {path}
============================================================
"""

MANUAL_HELP = """
How to get the session token manually:
  1. Log in to https://substack.com in your browser
  2. Open DevTools (Cmd+Option+I on Mac)
  3. Go to: Application -> Cookies -> https://substack.com
  4. Find the row 'substack.sid' and copy the Value
"""


def _prompt(label: str, *, hide: bool = False) -> str:
    if hide:
        import getpass
        return getpass.getpass(f"{label}: ").strip()
    return input(f"{label}: ").strip()


def _validate_publication_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")
    return f"{parsed.scheme}://{parsed.netloc}"


def _verify(creds: Credentials) -> bool:
    print("\nVerifying credentials...", flush=True)
    cookie_path = write_cookie_file(creds.session_token)
    try:
        api = SubstackApi(
            cookies_path=str(cookie_path),
            publication_url=creds.publication_url,
        )
        profile = api.get_user_profile()
        name = profile.get("name") or profile.get("email") or "(unknown)"
        print(f"  Authenticated as: {name}")
        return True
    except Exception as e:
        print(f"  Verification failed: {e}", file=sys.stderr)
        return False
    finally:
        cookie_path.unlink(missing_ok=True)


def _show_existing() -> None:
    creds = load_credentials()
    if creds is None:
        print("No credentials currently stored.")
        return
    print(f"Existing credentials found at: {CONFIG_FILE}")
    print(f"  Publication URL: {creds.publication_url}")
    print(f"  Session token:   {creds.session_token[:8]}...{creds.session_token[-4:]}")


def _confirm_overwrite(force: bool) -> bool:
    if force:
        return True
    answer = _prompt("\nProceed? Existing credentials will be overwritten. [y/N]")
    return answer.lower() in ("y", "yes")


def _manual_flow() -> int:
    print(MANUAL_HELP)
    try:
        raw_url = _prompt("Publication URL")
        publication_url = _validate_publication_url(raw_url)
        session_token = _prompt("Session token (substack.sid)", hide=True)
        if not session_token:
            print("Session token is required.", file=sys.stderr)
            return 1
    except KeyboardInterrupt:
        print("\nAborted.")
        return 130
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    creds = Credentials(publication_url=publication_url, session_token=session_token)
    if not _verify(creds):
        print(
            "\nCould not verify credentials. Common causes:\n"
            "  - Wrong session token (re-copy from DevTools)\n"
            "  - Wrong publication URL\n"
            "  - Token expired (log in to Substack again, then re-copy)",
            file=sys.stderr,
        )
        return 1
    save_credentials(creds)
    _print_next_steps()
    return 0


def _browser_flow() -> int:
    from .browser_setup import run_browser_setup

    creds = run_browser_setup()
    if creds is None:
        print(
            "\nBrowser auth failed. You can retry, or fall back to manual mode:\n"
            "  substack-mcp-setup --manual",
            file=sys.stderr,
        )
        return 1
    _print_next_steps()
    return 0


def _print_next_steps() -> None:
    print(
        "\nDone! Next: register the MCP server with Claude Code if you haven't:\n"
        "  claude mcp add substack-mcp --scope user -- "
        "/Users/$USER/substack/.venv/bin/substack-mcp\n"
        "Then restart Claude Code."
    )


def _chrome_flow(browser: str | None = None) -> int:
    from .chrome_setup import run_chrome_setup

    creds = run_chrome_setup(browser=browser)
    if creds is None:
        print(
            "\nChrome auto-detect failed. Falling back options:\n"
            "  substack-mcp-setup --browser   # Playwright (often blocked by Substack)\n"
            "  substack-mcp-setup --manual    # Paste cookie manually from DevTools",
            file=sys.stderr,
        )
        return 1
    _print_next_steps()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="substack-mcp-setup",
        description=(
            "Save Substack credentials for the MCP server. "
            "Default mode auto-detects your existing Chrome login."
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--chrome",
        action="store_true",
        help="(default) Read substack.sid from your existing Chrome session.",
    )
    mode.add_argument(
        "--browser",
        action="store_true",
        help="Launch Playwright Chromium and have you log in there. "
        "(Often triggers Substack's bot detection — use --chrome instead.)",
    )
    mode.add_argument(
        "--manual",
        action="store_true",
        help="Enter publication URL and substack.sid token by hand.",
    )
    parser.add_argument(
        "--from-browser",
        choices=["chrome", "brave", "chromium"],
        help="(with --chrome) Specific browser to read cookies from. "
        "Defaults to auto-detection across all supported browsers.",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip the overwrite confirmation prompt.",
    )
    args = parser.parse_args()

    print(BANNER.format(path=CONFIG_FILE))
    _show_existing()

    if not _confirm_overwrite(force=args.yes):
        print("Aborted.")
        sys.exit(0)

    if args.manual:
        sys.exit(_manual_flow())
    if args.browser:
        sys.exit(_browser_flow())
    # Default: --chrome
    sys.exit(_chrome_flow(browser=args.from_browser))


if __name__ == "__main__":
    main()
