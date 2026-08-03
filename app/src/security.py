import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta


TOKEN_TTL_MINUTES = int(os.getenv("TOKEN_TTL_MINUTES", "60"))
TOKEN_SECRET = os.getenv("TOKEN_SECRET", "dev-token-secret")


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(email: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": email,
        "exp": int((datetime.utcnow() + timedelta(minutes=TOKEN_TTL_MINUTES)).timestamp()),
    }
    header_part = _b64_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_part = _b64_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_part}.{payload_part}"
    signature = hmac.new(
        TOKEN_SECRET.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64_encode(signature)}"


def get_email_from_token(token: str) -> str | None:
    try:
        header_part, payload_part, signature_part = token.split(".")
        signing_input = f"{header_part}.{payload_part}"
        expected_signature = hmac.new(
            TOKEN_SECRET.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        actual_signature = _b64_decode(signature_part)

        if not hmac.compare_digest(expected_signature, actual_signature):
            return None

        header = json.loads(_b64_decode(header_part))
        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            return None

        payload = json.loads(_b64_decode(payload_part))
        if int(payload["exp"]) < int(datetime.utcnow().timestamp()):
            return None

        return payload["sub"]
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return None
