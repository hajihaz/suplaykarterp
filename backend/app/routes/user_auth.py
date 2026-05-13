from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from app.core.config import settings
from app.core.security import (
    attach_user_session_cookie,
    clear_user_session_cookie,
    create_user_session,
    delete_user_session,
    get_current_user,
    get_user_session_token,
    update_user_profile,
    upsert_google_user,
)
from app.schemas import (
    LogoutResponse,
    UserAuthConfigResponse,
    UserAuthResponse,
    UserGoogleLoginRequest,
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from app.services.conversations import claim_chat_session
from app.services.google_identity import verify_google_credential


router = APIRouter(prefix="/user-auth", tags=["user-auth"])
AVATAR_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_AVATAR_BYTES = 2 * 1024 * 1024


def _serialize_user_profile(user: dict) -> UserProfileResponse:
    return UserProfileResponse(
        id=int(user["id"]),
        email=str(user["email"]),
        name=str(user["name"]),
        username=str(user.get("username") or ""),
        picture_url=user.get("picture_url"),
        bio=str(user.get("bio") or ""),
        ai_nickname=str(user.get("ai_nickname") or "HajiHaz AI"),
        personality=user.get("personality") or "balanced",
        theme=user.get("theme") or "dark",
        memory_enabled=bool(user.get("memory_enabled", True)),
        ai_mode=user.get("ai_mode") or "auto",
        answer_mode=user.get("answer_mode") or "balanced",
        notifications_enabled=bool(user.get("notifications_enabled", False)),
    )


def _update_payload(payload: UserProfileUpdateRequest) -> dict:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(exclude_unset=True)
    return payload.dict(exclude_unset=True)


@router.get("/config", response_model=UserAuthConfigResponse)
def get_user_auth_config() -> UserAuthConfigResponse:
    return UserAuthConfigResponse(
        enabled=settings.google_login_enabled,
        client_id=settings.google_client_id or None,
        guest_mode=True,
    )


@router.post("/google", response_model=UserAuthResponse)
def google_login(payload: UserGoogleLoginRequest, response: Response) -> UserAuthResponse:
    profile = verify_google_credential(payload.credential)
    user = upsert_google_user(profile)
    claimed_session_id = claim_chat_session(payload.session_id, int(user["id"]))
    token = create_user_session(int(user["id"]))
    attach_user_session_cookie(response, token)
    return UserAuthResponse(
        token=token,
        user=_serialize_user_profile(user),
        claimed_session_id=claimed_session_id,
    )


@router.get("/me", response_model=UserProfileResponse)
def current_user_me(user: dict = Depends(get_current_user)) -> UserProfileResponse:
    return _serialize_user_profile(user)


@router.patch("/me", response_model=UserProfileResponse)
def update_current_user_profile(payload: UserProfileUpdateRequest, user: dict = Depends(get_current_user)) -> UserProfileResponse:
    updated = update_user_profile(int(user["id"]), _update_payload(payload))
    return _serialize_user_profile(updated)


@router.post("/avatar", response_model=UserProfileResponse)
async def upload_current_user_avatar(file: UploadFile = File(...), user: dict = Depends(get_current_user)) -> UserProfileResponse:
    suffix = AVATAR_CONTENT_TYPES.get(str(file.content_type or "").lower())
    if not suffix:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Avatar must be a JPG, PNG, WebP, or GIF image.")
    content = await file.read(MAX_AVATAR_BYTES + 1)
    if len(content) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=413, detail="Avatar must be 2 MB or smaller.")
    avatar_dir = settings.uploads_dir / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    avatar_path = avatar_dir / f"user-{int(user['id'])}{suffix}"
    avatar_path.write_bytes(content)
    updated = update_user_profile(int(user["id"]), {"picture_url": f"/uploads/avatars/{avatar_path.name}"})
    return _serialize_user_profile(updated)


@router.post("/logout", response_model=LogoutResponse)
def user_logout(response: Response, _: dict = Depends(get_current_user), token: str = Depends(get_user_session_token)) -> LogoutResponse:
    delete_user_session(token)
    clear_user_session_cookie(response)
    return LogoutResponse()
