"""GitHub Device Authorization Flow — token stored in Windows Credential Manager via keyring."""

import time
import webbrowser
from typing import Optional

import keyring
import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SERVICE = "timelog-github"
_ACCOUNT = "oauth-token"
_DEVICE_CODE_URL = "https://github.com/login/device/code"
_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
_SCOPE = "models:read"
CLIENT_ID = "Ov23lirZz2NYsizr5RFE"  # timelog GitHub OAuth App — public, not a secret


# ---------------------------------------------------------------------------
# Token storage (Windows Credential Manager)
# ---------------------------------------------------------------------------

def get_token() -> Optional[str]:
    """Return stored token, or None if not authenticated."""
    return keyring.get_password(_SERVICE, _ACCOUNT) or None


def save_token(token: str) -> None:
    """Persist token to Windows Credential Manager."""
    keyring.set_password(_SERVICE, _ACCOUNT, token)


def delete_token() -> None:
    """Remove stored token."""
    try:
        keyring.delete_password(_SERVICE, _ACCOUNT)
    except keyring.errors.PasswordDeleteError:
        pass


def is_authenticated() -> bool:
    return get_token() is not None


# ---------------------------------------------------------------------------
# Device flow
# ---------------------------------------------------------------------------

def login(client_id: str, open_browser: bool = True) -> str:
    """
    Run the GitHub Device Authorization Flow.

    Prints the user code, optionally opens the browser, polls until the user
    approves, stores the token, and returns it.

    Raises RuntimeError on failure (expired, denied, etc.).
    """
    # Step 1 — request device + user codes
    resp = requests.post(
        _DEVICE_CODE_URL,
        data={"client_id": client_id, "scope": _SCOPE},
        headers={"Accept": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    device_code: str = data["device_code"]
    user_code: str = data["user_code"]
    verification_uri: str = data["verification_uri"]
    expires_in: int = int(data.get("expires_in", 900))
    interval: int = int(data.get("interval", 5))

    # Step 2 — show the user what to do
    print(f"\n  Open: {verification_uri}")
    print(f"  Enter code: {user_code}\n")

    if open_browser:
        webbrowser.open(verification_uri)

    # Step 3 — poll until authorised, expired, or denied
    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
        token_resp = requests.post(
            _ACCESS_TOKEN_URL,
            data={
                "client_id": client_id,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        token_resp.raise_for_status()
        result = token_resp.json()

        error = result.get("error")

        if error == "authorization_pending":
            continue
        elif error == "slow_down":
            interval += 5
            continue
        elif error == "expired_token":
            raise RuntimeError("Authorization timed out. Run `timelog auth login` again.")
        elif error == "access_denied":
            raise RuntimeError("Authorization was denied.")
        elif error:
            raise RuntimeError(f"Unexpected error from GitHub: {error}")

        token: str = result["access_token"]
        save_token(token)
        return token

    raise RuntimeError("Authorization timed out. Run `timelog auth login` again.")
