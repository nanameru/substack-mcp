"""Compatibility stub: importing credentials from existing browsers is disabled.

The former dependency required an obsolete cryptography version. Use the
isolated browser or manual setup flow instead. This module never accesses
browser profiles or the OS keychain.
"""
from __future__ import annotations

import sys
from typing import Optional

from .auth import Credentials


def run_chrome_setup(browser: Optional[str] = None) -> Optional[Credentials]:
    """Return no credentials without opening browser profiles or keychains."""
    print("Existing browser cookie import is disabled. Use --browser or --manual.", file=sys.stderr)
    return None
