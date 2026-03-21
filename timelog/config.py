"""Configuration — all user data lives in ~/.timelog/ (AppData-style, no repo dependency)."""

from pathlib import Path
from dotenv import load_dotenv
import os

# ── User data directory ───────────────────────────────────────────────────────
CONFIG_DIR = Path.home() / ".timelog"
CONFIG_FILE = CONFIG_DIR / "config.env"
ACCOUNTS_MD = CONFIG_DIR / "accounts.md"

# Bundled accounts.md template (inside the package, used to seed on first init)
_TEMPLATE_ACCOUNTS_MD = Path(__file__).parent / "accounts_template.md"

# Load config: user config file first, then local .env (dev fallback)
CONFIG_DIR.mkdir(exist_ok=True)
load_dotenv(CONFIG_FILE)
load_dotenv()  # dev fallback — .env in cwd

# ── Settings ──────────────────────────────────────────────────────────────────
# GitHub OAuth App client ID — set interactively via `timelog init`
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")

COPILOT_MODEL = os.getenv("COPILOT_MODEL", "gpt-4o")
COPILOT_BASE_URL = "https://models.inference.ai.azure.com"

SAP_URL = os.getenv("SAP_URL", "")
SAP_USERNAME = os.getenv("SAP_USERNAME", "")
SAP_PASSWORD = os.getenv("SAP_PASSWORD", "")


def get_github_token() -> str:
    """Return GitHub token from keyring (OAuth flow) or env fallback."""
    from .auth import get_token as _keyring_token
    return _keyring_token() or os.getenv("GITHUB_TOKEN", "")


def save_config(values: dict[str, str]) -> None:
    """Write key=value pairs to ~/.timelog/config.env, merging with existing values."""
    existing: dict[str, str] = {}
    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()

    existing.update({k: v for k, v in values.items() if v})  # only write non-empty values

    lines = [f"{k}={v}" for k, v in existing.items()]
    CONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Reload into environment so the rest of the session sees the new values
    load_dotenv(CONFIG_FILE, override=True)
