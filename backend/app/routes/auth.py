from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from app.core.config import settings
from app.core.security import (
    attach_admin_session_cookie,
    authenticate_admin,
    change_admin_password,
    clear_admin_session_cookie,
    create_session,
    delete_session,
    get_current_admin,
    get_admin_profile,
    get_session_token,
    update_admin_profile,
)
from app.schemas import (
    AdminProfileUpdateRequest,
    AuthMeResponse,
    AuthResponse,
    LoginRequest,
    LogoutResponse,
    PasswordChangeRequest,
    PasswordChangeResponse,
)


router = APIRouter(prefix="/auth", tags=["auth"])
AVATAR_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_AVATAR_BYTES = 2 * 1024 * 1024


def _update_payload(payload: AdminProfileUpdateRequest) -> dict:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(exclude_unset=True)
    return payload.dict(exclude_unset=True)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, response: Response) -> AuthResponse:
    authenticated_email = authenticate_admin(payload.email, payload.password)
    if not authenticated_email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    token = create_session(authenticated_email)
    attach_admin_session_cookie(response, token)
    return AuthResponse(token=token, email=authenticated_email)


@router.get("/me", response_model=AuthMeResponse)
def me(email: str = Depends(get_current_admin)) -> AuthMeResponse:
    return AuthMeResponse(**get_admin_profile(email))


@router.patch("/profile", response_model=AuthMeResponse)
def update_profile(payload: AdminProfileUpdateRequest, email: str = Depends(get_current_admin)) -> AuthMeResponse:
    return AuthMeResponse(**update_admin_profile(email, _update_payload(payload)))


@router.post("/avatar", response_model=AuthMeResponse)
async def upload_admin_avatar(file: UploadFile = File(...), email: str = Depends(get_current_admin)) -> AuthMeResponse:
    suffix = AVATAR_CONTENT_TYPES.get(str(file.content_type or "").lower())
    if not suffix:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Avatar must be a JPG, PNG, WebP, or GIF image.")
    content = await file.read(MAX_AVATAR_BYTES + 1)
    if len(content) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=413, detail="Avatar must be 2 MB or smaller.")
    avatar_dir = settings.uploads_dir / "admin-avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    safe_name = email.replace("@", "-at-").replace(".", "-")
    avatar_path = avatar_dir / f"{safe_name}{suffix}"
    avatar_path.write_bytes(content)
    return AuthMeResponse(**update_admin_profile(email, {"avatar_url": f"/uploads/admin-avatars/{avatar_path.name}"}))


@router.post("/logout", response_model=LogoutResponse)
def logout(response: Response, _: str = Depends(get_current_admin), token: str = Depends(get_session_token)) -> LogoutResponse:
    delete_session(token)
    clear_admin_session_cookie(response)
    return LogoutResponse()


@router.post("/change-password", response_model=PasswordChangeResponse)
def change_password(payload: PasswordChangeRequest, email: str = Depends(get_current_admin)) -> PasswordChangeResponse:
    change_admin_password(email, payload.current_password, payload.new_password)
    return PasswordChangeResponse(email=email)
