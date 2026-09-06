"""Read-only production SNAP authentication check; never prints the token."""
import asyncio
import hashlib
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.modules.payments.doku_snap import DokuSnapClient
from app.core.exceptions import AppException
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


async def main():
    # Match the service WorkingDirectory, including relative .env/key paths.
    os.chdir(PROJECT_ROOT)
    try:
        client = DokuSnapClient()
    except (ValueError, OSError):
        print("FAIL: configuration cannot be loaded. Check .env syntax and read permissions.")
        return 1
    settings = client.settings
    print("Production host configured:", settings.DOKU_BASE_URL.rstrip("/") == "https://api.doku.com")
    print("Merchant and SNAP IDs match:", bool(settings.DOKU_CLIENT_ID) and settings.DOKU_CLIENT_ID == settings.DOKU_SNAP_PARTNER_ID)
    if settings.DOKU_BASE_URL.rstrip("/") != "https://api.doku.com":
        print("Stopped: configure production host before running this check.")
        return 1
    if settings.DOKU_SNAP_TOKEN_PATH != "/authorization/v1/access-token/b2b":
        print("FAIL: unexpected token path; no request sent.")
        return 1
    try:
        if not settings.DOKU_SNAP_PRIVATE_KEY_PATH:
            print("FAIL: DOKU_SNAP_PRIVATE_KEY_PATH is empty.")
            return 1
        key = serialization.load_pem_private_key(
            Path(settings.DOKU_SNAP_PRIVATE_KEY_PATH).expanduser().read_bytes(), password=None)
        if not isinstance(key, rsa.RSAPrivateKey) or key.key_size != 2048:
            print("FAIL: merchant private key must be RSA 2048.")
            return 1
        public_der = key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        print("Private key readable: True (RSA 2048)")
        print("Merchant public key SHA256 fingerprint:", hashlib.sha256(public_der).hexdigest())
        # Force a fresh request even if invoked from another Python process.
        DokuSnapClient._token = None
        DokuSnapClient._token_expires_at = None
        token = await client.access_token()
    except AppException as exc:
        print("Authentication failed:", exc.code)
        message = ("Cannot reach DOKU production; check DNS, firewall and TLS."
                   if exc.code == "DOKU_UNAVAILABLE" else str(exc.message))
        for value in (settings.DOKU_CLIENT_ID, settings.DOKU_SNAP_PARTNER_ID,
                      settings.DOKU_SECRET_KEY, settings.DOKU_SNAP_CLIENT_SECRET):
            if value:
                message = message.replace(value, "[redacted]")
        print("Message:", message)
        if exc.__cause__:
            print("Cause type:", type(exc.__cause__).__name__)
        return 1
    except (ValueError, OSError, TypeError) as exc:
        print("Local key/configuration error:", type(exc).__name__)
        return 1
    print("SNAP token received:", bool(token))
    print("No payment created. Token not displayed or saved.")
    print("This validates SNAP token authentication only, not channel activation or callbacks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
