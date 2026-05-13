from __future__ import annotations

from fastapi import HTTPException, status

from app.core.config import settings


def google_login_enabled() -> bool:
    return settings.google_login_enabled


def verify_google_credential(credential: str) -> dict:
    token_value = str(credential or "").strip()
    if not settings.google_login_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google login is not configured.")
    if not token_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google credential is required.")

    try:
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2 import id_token
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google login dependencies are not installed.",
        ) from exc

    try:
        payload = id_token.verify_oauth2_token(token_value, GoogleRequest(), settings.google_client_id)
    except Exception as exc:  # pragma: no cover - external verification details vary
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google sign-in could not be verified.") from exc

    issuer = str(payload.get("iss", "")).strip()
    if issuer not in {"https://accounts.google.com", "accounts.google.com"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google issuer is invalid.")

    google_sub = str(payload.get("sub", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    name = " ".join(str(payload.get("name") or payload.get("given_name") or email.split("@")[0]).split()).strip()
    picture_url = str(payload.get("picture", "")).strip() or None
    email_verified = bool(payload.get("email_verified"))

    if not google_sub or not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google account details are incomplete.")
    if not email_verified:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google email is not verified.")

    return {
        "google_sub": google_sub,
        "email": email,
        "name": name or email,
        "picture_url": picture_url,
        "email_verified": email_verified,
    }
