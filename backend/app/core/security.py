from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException, Response, status

from app.core.config import settings
from app.db import get_db

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
    from argon2.low_level import Type
except ImportError:  # pragma: no cover - only used when dependency installation is incomplete
    PasswordHasher = None  # type: ignore[assignment]
    InvalidHashError = VerificationError = VerifyMismatchError = Exception  # type: ignore[misc,assignment]
    Type = None  # type: ignore[assignment]


ADMIN_SESSION_COOKIE = "hajihaz_admin_session"
USER_SESSION_COOKIE = "hajihaz_user_session"
LEGACY_SHA256_PREFIX = "sha256:"
PBKDF2_PREFIX = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000
ADMIN_SELECT_FIELDS = """
    email, display_name, role_title, avatar_url, bio, timezone,
    notifications_enabled, created_at, updated_at
"""
USER_SELECT_FIELDS = """
    id, email, name, username, picture_url, bio, ai_nickname, personality,
    theme, memory_enabled, ai_mode, answer_mode, notifications_enabled, email_verified
"""

_PASSWORD_HASHER = (
    PasswordHasher(
        time_cost=3,
        memory_cost=65536,
        parallelism=2,
        hash_len=32,
        salt_len=16,
        type=Type.ID,
    )
    if PasswordHasher is not None and Type is not None
    else None
)


def _hash_password_pbkdf2(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return f"{PBKDF2_PREFIX}${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def _verify_pbkdf2(candidate: str, stored_hash: str) -> bool:
    try:
        prefix, iterations, salt, digest = stored_hash.split("$", 3)
        if prefix != PBKDF2_PREFIX:
            return False
        calculated = hashlib.pbkdf2_hmac("sha256", candidate.encode("utf-8"), bytes.fromhex(salt), int(iterations))
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(calculated.hex(), digest)


def hash_password(password: str) -> str:
    if _PASSWORD_HASHER is None:
        return _hash_password_pbkdf2(password)
    return _PASSWORD_HASHER.hash(password)


def normalize_admin_email(email: str) -> str:
    return " ".join(str(email).split()).strip().lower()


def _initial_admin_password_hash() -> str:
    if settings.admin_password_hash:
        return settings.admin_password_hash.strip()
    return hash_password(settings.admin_password)


def verify_password_hash(candidate: str, expected_hash: str) -> bool:
    normalized_hash = expected_hash.strip()
    if not normalized_hash:
        return False
    if normalized_hash.startswith("$argon2"):
        if _PASSWORD_HASHER is None:
            return False
        try:
            return _PASSWORD_HASHER.verify(normalized_hash, candidate)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False
    if normalized_hash.startswith(f"{PBKDF2_PREFIX}$"):
        return _verify_pbkdf2(candidate, normalized_hash)

    legacy_hash = normalized_hash.removeprefix(LEGACY_SHA256_PREFIX).lower()
    candidate_hash = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
    return hmac.compare_digest(candidate_hash, legacy_hash)


def password_hash_needs_rehash(stored_hash: str) -> bool:
    normalized_hash = stored_hash.strip()
    if not normalized_hash.startswith("$argon2"):
        if normalized_hash.startswith(f"{PBKDF2_PREFIX}$") and _PASSWORD_HASHER is None:
            try:
                return int(normalized_hash.split("$", 3)[1]) < PBKDF2_ITERATIONS
            except (IndexError, ValueError):
                return True
        return True
    return True if _PASSWORD_HASHER is None else _PASSWORD_HASHER.check_needs_rehash(normalized_hash)


def verify_admin_password(candidate: str) -> bool:
    if settings.admin_password_hash:
        return verify_password_hash(candidate, settings.admin_password_hash)
    return hmac.compare_digest(candidate, settings.admin_password)


def attach_admin_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        ADMIN_SESSION_COOKIE,
        token,
        max_age=max(1, settings.session_ttl_hours) * 3600,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.safe_auth_cookie_samesite,
        path="/",
    )


def attach_user_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        USER_SESSION_COOKIE,
        token,
        max_age=max(1, settings.user_session_ttl_hours) * 3600,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.safe_auth_cookie_samesite,
        path="/",
    )


def clear_admin_session_cookie(response: Response) -> None:
    response.delete_cookie(ADMIN_SESSION_COOKIE, path="/", samesite=settings.safe_auth_cookie_samesite)


def clear_user_session_cookie(response: Response) -> None:
    response.delete_cookie(USER_SESSION_COOKIE, path="/", samesite=settings.safe_auth_cookie_samesite)


def _session_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=max(1, settings.session_ttl_hours))


def _user_session_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=max(1, settings.user_session_ttl_hours))


def _hash_token(token: str) -> str:
    material = f"{settings.secret_key}:{token}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def clear_expired_sessions() -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (datetime.now(timezone.utc).isoformat(),))
        conn.commit()


def clear_expired_user_sessions() -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM user_sessions WHERE expires_at < ?", (datetime.now(timezone.utc).isoformat(),))
        conn.commit()


def ensure_primary_admin(password_hash: str | None = None) -> None:
    email = normalize_admin_email(settings.admin_email)
    if not email:
        return

    with get_db() as conn:
        row = conn.execute("SELECT id FROM admins WHERE email = ?", (email,)).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO admins (email, password_hash)
                VALUES (?, ?)
                """,
                (email, password_hash or _initial_admin_password_hash()),
            )
            conn.commit()


def authenticate_admin(email: str, password: str) -> str | None:
    normalized_email = normalize_admin_email(email)
    if not normalized_email:
        return None

    with get_db() as conn:
        row = conn.execute(
            """
            SELECT email, password_hash
            FROM admins
            WHERE email = ?
            """,
            (normalized_email,),
        ).fetchone()

    if row is not None:
        if verify_password_hash(password, str(row["password_hash"])):
            if password_hash_needs_rehash(str(row["password_hash"])):
                with get_db() as conn:
                    conn.execute(
                        """
                        UPDATE admins
                        SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE email = ?
                        """,
                        (hash_password(password), normalized_email),
                    )
                    conn.commit()
            return str(row["email"])
        return None

    if normalized_email == normalize_admin_email(settings.admin_email) and verify_admin_password(password):
        ensure_primary_admin(password_hash=hash_password(password))
        return normalized_email

    return None


def list_admin_users(current_email: str | None = None) -> list[dict]:
    normalized_current = normalize_admin_email(current_email or "")
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT email, display_name, role_title, avatar_url, created_at, updated_at
            FROM admins
            ORDER BY email ASC
            """
        ).fetchall()

    return [
        {
            "email": str(row["email"]),
            "display_name": str(row["display_name"] or ""),
            "role_title": str(row["role_title"] or "Workspace operator"),
            "avatar_url": row["avatar_url"],
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "is_current": str(row["email"]) == normalized_current,
        }
        for row in rows
    ]


def _serialize_admin_row(row) -> dict:
    email = str(row["email"])
    display_name = str(row["display_name"] or "").strip() or email.split("@", 1)[0].replace(".", " ").title()
    return {
        "email": email,
        "display_name": display_name,
        "role_title": str(row["role_title"] or "Workspace operator"),
        "avatar_url": row["avatar_url"],
        "bio": str(row["bio"] or ""),
        "timezone": str(row["timezone"] or ""),
        "notifications_enabled": bool(row["notifications_enabled"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def get_admin_profile(email: str) -> dict:
    normalized_email = normalize_admin_email(email)
    if not normalized_email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin email is required.")
    with get_db() as conn:
        row = conn.execute(f"SELECT {ADMIN_SELECT_FIELDS} FROM admins WHERE email = ?", (normalized_email,)).fetchone()
    if row is None:
        ensure_primary_admin()
        with get_db() as conn:
            row = conn.execute(f"SELECT {ADMIN_SELECT_FIELDS} FROM admins WHERE email = ?", (normalized_email,)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin account not found.")
    return _serialize_admin_row(row)


def update_admin_profile(email: str, updates: dict) -> dict:
    normalized_email = normalize_admin_email(email)
    allowed = {
        "display_name": lambda value: _clean_profile_text(value, maximum=80, fallback=normalized_email.split("@", 1)[0]),
        "role_title": lambda value: _clean_profile_text(value, maximum=80, fallback="Workspace operator"),
        "avatar_url": lambda value: _clean_profile_text(value, maximum=500),
        "bio": lambda value: _clean_profile_text(value, maximum=500),
        "timezone": lambda value: _clean_profile_text(value, maximum=80),
        "notifications_enabled": lambda value: 1 if bool(value) else 0,
    }
    assignments = []
    values = []
    for key, cleaner in allowed.items():
        if key in updates and updates[key] is not None:
            assignments.append(f"{key} = ?")
            values.append(cleaner(updates[key]))
    if assignments:
        values.append(normalized_email)
        with get_db() as conn:
            conn.execute(
                f"""
                UPDATE admins
                SET {", ".join(assignments)}, updated_at = CURRENT_TIMESTAMP
                WHERE email = ?
                """,
                tuple(values),
            )
            conn.commit()
    return get_admin_profile(normalized_email)


def create_admin_user(email: str, password: str) -> dict:
    normalized_email = normalize_admin_email(email)
    if not normalized_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin email is required.")

    with get_db() as conn:
        existing = conn.execute("SELECT email FROM admins WHERE email = ?", (normalized_email,)).fetchone()
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That admin email already exists.")
        conn.execute(
            """
            INSERT INTO admins (email, password_hash)
            VALUES (?, ?)
            """,
            (normalized_email, hash_password(password)),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT email, display_name, role_title, avatar_url, created_at, updated_at
            FROM admins
            WHERE email = ?
            """,
            (normalized_email,),
        ).fetchone()

    return {
        "email": str(row["email"]),
        "display_name": str(row["display_name"] or ""),
        "role_title": str(row["role_title"] or "Workspace operator"),
        "avatar_url": row["avatar_url"],
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "is_current": False,
    }


def change_admin_password(email: str, current_password: str, new_password: str) -> None:
    normalized_email = normalize_admin_email(email)
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT password_hash
            FROM admins
            WHERE email = ?
            """,
            (normalized_email,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin account not found.")
        if not verify_password_hash(current_password, str(row["password_hash"])):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect.")
        conn.execute(
            """
            UPDATE admins
            SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
            WHERE email = ?
            """,
            (hash_password(new_password), normalized_email),
        )
        conn.commit()


def create_session(email: str) -> str:
    clear_expired_sessions()
    token = secrets.token_urlsafe(32)
    expires_at = _session_expiry()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO sessions (token, email, expires_at)
            VALUES (?, ?, ?)
            """,
            (_hash_token(token), email, expires_at.isoformat()),
        )
        conn.commit()
    return token


def upsert_google_user(profile: dict) -> dict:
    google_sub = str(profile.get("google_sub", "")).strip()
    email = normalize_admin_email(profile.get("email", ""))
    name = " ".join(str(profile.get("name", "")).split()).strip()
    picture_url = str(profile.get("picture_url", "")).strip() or None
    email_verified = 1 if bool(profile.get("email_verified")) else 0
    if not google_sub or not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google account details are incomplete.")

    with get_db() as conn:
        existing = conn.execute(
            """
            SELECT id
            FROM users
            WHERE google_sub = ?
            """,
            (google_sub,),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO users (google_sub, email, name, picture_url, email_verified)
                VALUES (?, ?, ?, ?, ?)
                """,
                (google_sub, email, name, picture_url, email_verified),
            )
        else:
            conn.execute(
                """
                UPDATE users
                SET email = ?, name = ?, picture_url = ?, email_verified = ?, updated_at = CURRENT_TIMESTAMP
                WHERE google_sub = ?
                """,
                (email, name, picture_url, email_verified, google_sub),
            )
        conn.commit()
        row = conn.execute(
            """
            SELECT
                id, email, name, username, picture_url, bio, ai_nickname, personality,
                theme, memory_enabled, ai_mode, answer_mode, notifications_enabled, email_verified
            FROM users
            WHERE google_sub = ?
            """,
            (google_sub,),
        ).fetchone()

    return _serialize_user_row(row)


def _serialize_user_row(row) -> dict:
    return {
        "id": int(row["id"]),
        "email": str(row["email"]),
        "name": str(row["name"] or row["email"]),
        "username": str(row["username"] or ""),
        "picture_url": row["picture_url"],
        "bio": str(row["bio"] or ""),
        "ai_nickname": str(row["ai_nickname"] or "HajiHaz AI"),
        "personality": str(row["personality"] or "balanced"),
        "theme": str(row["theme"] or "dark"),
        "memory_enabled": bool(row["memory_enabled"]),
        "ai_mode": str(row["ai_mode"] or "auto"),
        "answer_mode": str(row["answer_mode"] or "balanced"),
        "notifications_enabled": bool(row["notifications_enabled"]),
        "email_verified": bool(row["email_verified"]),
    }


def _clean_profile_text(value: Optional[str], *, maximum: int, fallback: str = "") -> str:
    cleaned = " ".join(str(value or "").split()).strip()
    return (cleaned or fallback)[:maximum]


def _clean_username(value: Optional[str]) -> str:
    cleaned = str(value or "").strip().lower()
    cleaned = re.sub(r"[^a-z0-9._-]+", "", cleaned)
    return cleaned[:40]


def update_user_profile(user_id: int, updates: dict) -> dict:
    allowed = {
        "name": lambda value: _clean_profile_text(value, maximum=80, fallback="Haji"),
        "username": _clean_username,
        "picture_url": lambda value: _clean_profile_text(value, maximum=500),
        "bio": lambda value: _clean_profile_text(value, maximum=500),
        "ai_nickname": lambda value: _clean_profile_text(value, maximum=80, fallback="HajiHaz AI"),
        "personality": lambda value: value if value in {"balanced", "direct", "warm", "strategic", "creative"} else "balanced",
        "theme": lambda value: value if value in {"dark", "light", "system"} else "dark",
        "memory_enabled": lambda value: 1 if bool(value) else 0,
        "ai_mode": lambda value: value if value in {"auto", "general", "memory", "reasoning", "coding", "creative"} else "auto",
        "answer_mode": lambda value: value if value in {"balanced", "concise", "detailed", "strategic", "founder"} else "balanced",
        "notifications_enabled": lambda value: 1 if bool(value) else 0,
    }
    assignments = []
    values = []
    for key, cleaner in allowed.items():
        if key in updates and updates[key] is not None:
            assignments.append(f"{key} = ?")
            values.append(cleaner(updates[key]))
    if assignments:
        values.append(int(user_id))
        with get_db() as conn:
            conn.execute(
                f"""
                UPDATE users
                SET {", ".join(assignments)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                tuple(values),
            )
            conn.commit()
    with get_db() as conn:
        row = conn.execute(f"SELECT {USER_SELECT_FIELDS} FROM users WHERE id = ?", (int(user_id),)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return _serialize_user_row(row)


def create_user_session(user_id: int) -> str:
    clear_expired_user_sessions()
    token = secrets.token_urlsafe(32)
    expires_at = _user_session_expiry()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO user_sessions (token, user_id, expires_at)
            VALUES (?, ?, ?)
            """,
            (_hash_token(token), user_id, expires_at.isoformat()),
        )
        conn.commit()
    return token


def delete_user_session(token: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM user_sessions WHERE token = ?", (_hash_token(token),))
        conn.commit()
    return cursor.rowcount > 0


def delete_session(token: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM sessions WHERE token = ?", (_hash_token(token),))
        conn.commit()
    return cursor.rowcount > 0


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization header.")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization scheme.")
    token = authorization[len(prefix):].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    return token


def _extract_auth_token(authorization: Optional[str], cookie_token: Optional[str]) -> str:
    if authorization:
        return _extract_bearer_token(authorization)
    if cookie_token and cookie_token.strip():
        return cookie_token.strip()
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization header.")


def get_session_token(
    authorization: Optional[str] = Header(default=None),
    session_cookie: Optional[str] = Cookie(default=None, alias=ADMIN_SESSION_COOKIE),
) -> str:
    return _extract_auth_token(authorization, session_cookie)


def get_user_session_token(
    authorization: Optional[str] = Header(default=None),
    session_cookie: Optional[str] = Cookie(default=None, alias=USER_SESSION_COOKIE),
) -> str:
    return _extract_auth_token(authorization, session_cookie)


def get_current_admin(
    authorization: Optional[str] = Header(default=None),
    session_cookie: Optional[str] = Cookie(default=None, alias=ADMIN_SESSION_COOKIE),
) -> str:
    clear_expired_sessions()
    raw_token = _extract_auth_token(authorization, session_cookie)
    hashed_token = _hash_token(raw_token)
    refreshed_expiry = _session_expiry().isoformat()
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT email, expires_at
            FROM sessions
            WHERE token = ?
            """,
            (hashed_token,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not found.")
        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at < datetime.now(timezone.utc):
            conn.execute("DELETE FROM sessions WHERE token = ?", (hashed_token,))
            conn.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired.")
        conn.execute("UPDATE sessions SET expires_at = ? WHERE token = ?", (refreshed_expiry, hashed_token))
        conn.commit()
    return str(row["email"])


def _load_current_user(raw_token: str) -> dict:
    clear_expired_user_sessions()
    hashed_token = _hash_token(raw_token)
    refreshed_expiry = _user_session_expiry().isoformat()
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT
                users.id,
                users.email,
                users.name,
                users.username,
                users.picture_url,
                users.bio,
                users.ai_nickname,
                users.personality,
                users.theme,
                users.memory_enabled,
                users.ai_mode,
                users.answer_mode,
                users.notifications_enabled,
                users.email_verified,
                user_sessions.expires_at
            FROM user_sessions
            JOIN users ON users.id = user_sessions.user_id
            WHERE user_sessions.token = ?
            """,
            (hashed_token,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User session not found.")
        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at < datetime.now(timezone.utc):
            conn.execute("DELETE FROM user_sessions WHERE token = ?", (hashed_token,))
            conn.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User session expired.")
        conn.execute("UPDATE user_sessions SET expires_at = ? WHERE token = ?", (refreshed_expiry, hashed_token))
        conn.commit()

    return _serialize_user_row(row)


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    session_cookie: Optional[str] = Cookie(default=None, alias=USER_SESSION_COOKIE),
) -> dict:
    return _load_current_user(_extract_auth_token(authorization, session_cookie))


def get_optional_current_user(
    authorization: Optional[str] = Header(default=None),
    session_cookie: Optional[str] = Cookie(default=None, alias=USER_SESSION_COOKIE),
) -> dict | None:
    if not authorization and not session_cookie:
        return None
    return _load_current_user(_extract_auth_token(authorization, session_cookie))


AdminEmail = Depends(get_current_admin)
