"""Authentication and credential storage for Substack MCP."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from platformdirs import user_config_dir

CONFIG_DIR = Path(user_config_dir("substack-mcp", appauthor=False))
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Credentials:
    publication_url: str
    session_token: str

    def to_dict(self) -> dict:
        return {
            "publication_url": self.publication_url,
            "session_token": self.session_token,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Credentials":
        return cls(
            publication_url=data["publication_url"],
            session_token=data["session_token"],
        )


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, stat.S_IRWXU)


def save_credentials(creds: Credentials) -> Path:
    _ensure_config_dir()
    CONFIG_FILE.write_text(json.dumps(creds.to_dict(), indent=2))
    os.chmod(CONFIG_FILE, stat.S_IRUSR | stat.S_IWUSR)
    return CONFIG_FILE


def load_credentials() -> Optional[Credentials]:
    pub_url = os.environ.get("SUBSTACK_PUBLICATION_URL")
    token = os.environ.get("SUBSTACK_SESSION_TOKEN")
    if pub_url and token:
        return Credentials(publication_url=pub_url, session_token=token)

    if not CONFIG_FILE.exists():
        return None

    try:
        data = json.loads(CONFIG_FILE.read_text())
        return Credentials.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None


def clear_credentials() -> None:
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()


def write_cookie_file(session_token: str) -> Path:
    fd, path = tempfile.mkstemp(suffix=".json", prefix="substack-mcp-")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "w") as f:
            json.dump({"substack.sid": session_token}, f)
    except Exception:
        os.close(fd)
        Path(path).unlink(missing_ok=True)
        raise
    return Path(path)
