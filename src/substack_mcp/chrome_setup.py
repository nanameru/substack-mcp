"""Read substack.sid directly from the user's existing Chrome session.

This is the most reliable auth method:
  - No browser automation -> Substack can't detect anything unusual.
  - User just needs to be logged in to Substack in Chrome (which they already are).
  - One-time keychain prompt to allow reading Chrome's encrypted cookies.

Falls back gracefully if Chrome isn't installed, isn't logged in, or the user
denies keychain access.
"""

from __future__ import annotations

import sys
from typing import Optional

import requests

from .auth import Credentials, save_credentials

SUBSTACK_URL = "https://substack.com"
PROFILE_ENDPOINT = "https://substack.com/api/v1/user/profile/self"
SUPPORTED_BROWSERS = ("chrome", "brave", "chromium")


def _try_browser(browser_name: str) -> Optional[str]:
    """Attempt to read substack.sid from the named browser. Returns None on failure."""
    try:
        from pycookiecheat import BrowserType, chrome_cookies
    except ImportError:
        print("pycookiecheat not installed.", file=sys.stderr)
        return None

    browser_map = {
        "chrome": BrowserType.CHROME,
        "brave": BrowserType.BRAVE,
        "chromium": BrowserType.CHROMIUM,
    }
    btype = browser_map.get(browser_name)
    if btype is None:
        print(f"  [{browser_name}] not supported by pycookiecheat 0.8.", file=sys.stderr)
        return None

    try:
        cookies = chrome_cookies(SUBSTACK_URL, browser=btype)
    except Exception as e:
        msg = str(e)
        if any(k in msg.lower() for k in ("encrypted", "password", "keychain")):
            print(
                f"  [{browser_name}] keychain access denied or unavailable.",
                file=sys.stderr,
            )
        elif any(k in msg.lower() for k in ("no such", "not found")):
            print(f"  [{browser_name}] not installed or never used.", file=sys.stderr)
        else:
            print(f"  [{browser_name}] error: {msg}", file=sys.stderr)
        return None

    sid = cookies.get("substack.sid") or cookies.get("connect.sid")
    if not sid:
        print(
            f"  [{browser_name}] not logged in to Substack (no substack.sid cookie).",
            file=sys.stderr,
        )
        return None
    if len(sid) < 20:
        print(f"  [{browser_name}] cookie value looks too short.", file=sys.stderr)
        return None
    return sid


def _fetch_profile(session_token: str) -> Optional[dict]:
    s = requests.Session()
    s.cookies.update({"substack.sid": session_token})
    try:
        r = s.get(PROFILE_ENDPOINT, timeout=10)
        if r.status_code != 200:
            print(
                f"  Profile request returned status {r.status_code}.",
                file=sys.stderr,
            )
            return None
        return r.json()
    except Exception as e:
        print(f"  Profile request failed: {e}", file=sys.stderr)
        return None


def _publication_url_from(publication: dict) -> Optional[str]:
    if not publication:
        return None
    custom = publication.get("custom_domain")
    if custom:
        return f"https://{custom}"
    subdomain = publication.get("subdomain")
    if subdomain:
        return f"https://{subdomain}.substack.com"
    return None


def _resolve_publication_url(profile: dict) -> Optional[str]:
    primary = profile.get("primaryPublication")
    url = _publication_url_from(primary) if primary else None
    if url:
        return url
    pubusers = profile.get("publicationUsers") or []
    for pu in pubusers:
        if pu.get("is_primary"):
            pub_url = _publication_url_from(pu.get("publication") or {})
            if pub_url:
                return pub_url
    for pu in pubusers:
        pub_url = _publication_url_from(pu.get("publication") or {})
        if pub_url:
            return pub_url
    return None


def run_chrome_setup(browser: Optional[str] = None) -> Optional[Credentials]:
    """Try to read substack.sid from the user's existing browser cookies.

    Args:
        browser: Specific browser name to try, or None to auto-try common ones.

    Returns:
        Credentials on success, None on any failure.
    """
    print("\n=== Auto-detect from existing browser session ===")
    print(
        "Reading the substack.sid cookie from a browser where you're already\n"
        "logged in to Substack. macOS may show a Keychain access prompt — click\n"
        "'Allow' or 'Always Allow' for 'Chrome Safe Storage' (or similar).\n"
    )

    browsers_to_try = [browser] if browser else list(SUPPORTED_BROWSERS)

    sid: Optional[str] = None
    for name in browsers_to_try:
        print(f"Trying {name}...")
        sid = _try_browser(name)
        if sid:
            print(f"  Found substack.sid in {name}.")
            break

    if not sid:
        print(
            "\nCould not find a Substack session in any installed browser.\n"
            "Make sure you're logged in to https://substack.com in Chrome (or Brave),\n"
            "then try again.",
            file=sys.stderr,
        )
        return None

    print("\nLooking up your account and primary publication...")
    profile = _fetch_profile(sid)
    if profile is None:
        print(
            "\nCould not call the Substack API with the captured cookie.\n"
            "The cookie may have expired — log out and back in to Substack in Chrome,\n"
            "then re-run setup.",
            file=sys.stderr,
        )
        return None

    name = profile.get("name") or profile.get("email") or "(unknown)"
    print(f"  Authenticated as: {name} (user_id={profile.get('id')})")

    publication_url = _resolve_publication_url(profile)
    if publication_url:
        primary = profile.get("primaryPublication") or {}
        pub_name = primary.get("name") or "(unnamed)"
        print(f"  Publication: {pub_name} -> {publication_url}")
    else:
        print(
            "\nNo Substack publication found on your account. Create one at:\n"
            "  https://substack.com/dashboard\n"
            "(click 'Start a Substack' / 'New publication'), then re-run setup.",
            file=sys.stderr,
        )
        return None

    creds = Credentials(publication_url=publication_url, session_token=sid)
    path = save_credentials(creds)
    print(f"\nSaved to: {path}")
    return creds
