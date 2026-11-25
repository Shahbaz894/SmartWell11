# app/core/security.py

from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.services.jwt_handler import JWTHandler
from app.core.exceptions import AppException
from app.core.logger import logger

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db:    Session = Depends(get_db),
) -> User:
    """
    Validate JWT Bearer token and return the authenticated User.

    Raises:
        AppException: 401 if token is missing, invalid, expired,
                      or the user no longer exists in the DB.
    """

    # ── 1. Decode & validate token ────────────────────────────────────────────
    try:
        payload = JWTHandler.decode_token(token)
    except AppException:
        raise  # already a clean 401 — let it go
    except Exception as exc:
        logger.error("JWT decode failed: %s", repr(exc), exc_info=True)
        raise AppException(401, "Invalid or expired token")

    # ── 2. Extract subject (user_id) ──────────────────────────────────────────
    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise AppException(401, "Invalid token subject") from exc

    try:
        user = db.query(User).filter(User.id == user_id).first()
    except Exception as exc:
        logger.error(
            "DB error during auth | user_id=%s error=%s",
            user_id, repr(exc), exc_info=True,
        )
        raise AppException(500, "Authentication service error")

    if not user:
        logger.warning("Authenticated user_id not found in DB | user_id=%s", user_id)
        raise AppException(401, "User not found")

    if not user.is_active:
        raise AppException(403, "Account disabled")
    if not JWTHandler.matches_password(payload, user):
        raise AppException(401, "Sign in again")

    logger.debug("User authenticated | user_id=%s email=%s", user.id, user.email)
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {"admin", "super_admin"}:
        raise AppException(403, "Administrator access required")
    return current_user



def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "super_admin":
        raise AppException(403, "Super administrator access required")
    return current_user
