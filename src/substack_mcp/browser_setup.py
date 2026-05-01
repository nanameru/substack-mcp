"""Playwright-based browser auth — user logs in to Substack, we capture the cookie.

Flow:
  1. Launch a visible Chromium window pointing at substack.com/sign-in.
  2. Wait for the `substack.sid` cookie to appear (= login successful).
  3. Extract the cookie, look up the user's primary publication via the API,
     and save credentials.

The browser stays open until the user finishes logging in or closes it.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Optional

from substack import Api as SubstackApi

from .auth import Credentials, save_credentials, write_cookie_file

LOGIN_URL = "https://substack.com/sign-in"
SUCCESS_DOMAINS = ("substack.com",)
DEFAULT_TIMEOUT_SECONDS = 300  # 5 minutes


async def _wait_for_login(context, timeout_s: int) -> Optional[str]:
    """Poll cookies until substack.sid appears, or until timeout."""
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        cookies = await context.cookies()
        for c in cookies:
            if c.get("name") == "substack.sid" and c.get("value"):
                value = c["value"]
                if len(value) > 20:
                    return value
        await asyncio.sleep(1)
    return None


async def _run_browser_auth(timeout_s: int) -> Optional[str]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print(
            "Playwright is not installed. Install with: uv pip install playwright",
            file=sys.stderr,
        )
        return None

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=False)
        except Exception as e:
            msg = str(e)
            if "Executable doesn't exist" in msg or "playwright install" in msg.lower():
                print(
                    "\nChromium is not installed. Run:\n"
                    "  .venv/bin/playwright install chromium\n",
                    file=sys.stderr,
                )
            else:
                print(f"\nFailed to launch browser: {e}", file=sys.stderr)
            return None

        context = await browser.new_context()
        page = await context.new_page()

        print("\nOpening Substack sign-in page in a new window...")
        print(
            f"Please log in. Waiting up to {timeout_s // 60} minutes for login to complete."
        )
        print("(After login, you can close the browser yourself or it will close automatically.)")

        await page.goto(LOGIN_URL)

        token = await _wait_for_login(context, timeout_s)

        try:
            await browser.close()
        except Exception:
            pass

        return token


def _resolve_publication_url(session_token: str) -> Optional[str]:
    """Use python-substack to look up the user's primary publication URL."""
    cookie_path = write_cookie_file(session_token)
    try:
        # publication_url is required by SubstackApi.__init__, but the value
        # gets overwritten by primary publication lookup. Pass a placeholder.
        try:
            api = SubstackApi(
                cookies_path=str(cookie_path),
                publication_url="https://substack.com",
            )
            return api.publication_url.replace("/api/v1", "").rstrip("/")
        except Exception as e:
            print(f"Could not auto-detect publication URL: {e}", file=sys.stderr)
            return None
    finally:
        cookie_path.unlink(missing_ok=True)


def run_browser_setup(timeout_s: int = DEFAULT_TIMEOUT_SECONDS) -> Optional[Credentials]:
    """Entry point. Launches browser, waits for login, returns Credentials or None."""
    print("\n=== Browser-based authentication ===")
    print("A Chromium window will open. Log in to your Substack account there.")

    try:
        token = asyncio.run(_run_browser_auth(timeout_s))
    except KeyboardInterrupt:
        print("\nAborted.")
        return None

    if not token:
        print("\nNo login detected (timeout or browser closed before login).", file=sys.stderr)
        return None

    print("Login captured. Looking up your primary publication...")
    publication_url = _resolve_publication_url(token)
    if not publication_url:
        # Fallback: ask the user
        print(
            "Could not auto-detect your publication URL.\n"
            "Please enter it manually (e.g., https://yourname.substack.com)."
        )
        try:
            publication_url = input("Publication URL: ").strip()
        except (KeyboardInterrupt, EOFError):
            return None
        if not publication_url:
            return None
        if not publication_url.startswith(("http://", "https://")):
            publication_url = "https://" + publication_url

    creds = Credentials(publication_url=publication_url, session_token=token)

    # Verify by fetching profile
    cookie_path = write_cookie_file(token)
    try:
        api = SubstackApi(
            cookies_path=str(cookie_path),
            publication_url=publication_url,
        )
        profile = api.get_user_profile()
        name = profile.get("name") or profile.get("email") or "(unknown)"
        print(f"Authenticated as: {name}")
        print(f"Publication: {publication_url}")
    except Exception as e:
        print(f"Could not verify credentials: {e}", file=sys.stderr)
        return None
    finally:
        cookie_path.unlink(missing_ok=True)

    path = save_credentials(creds)
    print(f"\nSaved to: {path}")
    return creds
