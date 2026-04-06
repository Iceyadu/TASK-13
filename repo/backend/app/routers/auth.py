from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.audit import RevokedToken
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, TokenUser, RefreshRequest, RefreshResponse, PasswordChangeRequest
from app.schemas.common import MessageResponse
from app.services.auth_service import verify_password, hash_password, create_access_token, create_refresh_token, decode_token
from app.services.audit_service import log_audit

router = APIRouter(prefix="/auth", tags=["auth"])


async def _is_token_revoked(db: AsyncSession, jti: str) -> bool:
    """Check if a token JTI has been revoked."""
    result = await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
    return result.scalar_one_or_none() is not None


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalars().first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    token_data = {"sub": str(user.id), "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    await log_audit(db, user_id=user.id, action="LOGIN", resource_type="user", resource_id=user.id)
    await db.commit()
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=1800,
        user=TokenUser.model_validate(user),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    from jose import JWTError
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        # Check if the refresh token has been revoked
        jti = payload.get("jti")
        if jti and await _is_token_revoked(db, jti):
            raise HTTPException(status_code=401, detail="Token has been revoked")
        new_access = create_access_token({"sub": payload["sub"], "role": payload.get("role", "")})
        return RefreshResponse(access_token=new_access, expires_in=1800)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")


@router.post("/logout", status_code=204)
async def logout(
    body: RefreshRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout and revoke the refresh token if provided."""
    if body and body.refresh_token:
        from jose import JWTError
        try:
            payload = decode_token(body.refresh_token)
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
                revoked = RevokedToken(
                    jti=jti,
                    user_id=current_user.id,
                    revoked_at=datetime.now(timezone.utc),
                    expires_at=expires_at,
                )
                db.add(revoked)
                await db.commit()
        except (JWTError, Exception):
            pass  # Best-effort revocation; don't fail logout
    return None


@router.put("/password", response_model=MessageResponse)
async def change_password(body: PasswordChangeRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.password_hash = hash_password(body.new_password)
    await db.commit()
    return MessageResponse(message="Password updated successfully")


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {"id": str(current_user.id), "username": current_user.username, "role": current_user.role, "canary_enabled": current_user.canary_enabled}
