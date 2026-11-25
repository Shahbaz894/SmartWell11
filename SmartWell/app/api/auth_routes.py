from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user, require_admin, require_super_admin
from app.models.user import User
from app.schemas.user_schema import (
    UserCreate,
    UserLogin,
    UserResponse,
    PasswordChange,
    AccountDelete,
    AccountCreate,
    PasswordReset,
)
from app.services.auth_service import AuthService
from app.services.device_service import DeviceService
from app.repositories.user_repo import UserRepository

router = APIRouter(tags=["Authentication & Accounts"])


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    return AuthService.register(db, user_in)


@router.post("/auth/login")
def login(creds: UserLogin, db: Session = Depends(get_db)):
    return AuthService.login(db, creds.email, creds.password)


@router.post("/auth/token")
def login_form(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return AuthService.login(db, form.username, form.password)


@router.get("/account/me", response_model=UserResponse)
def get_account(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/account/password")
def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return AuthService.change_password(db, current_user.id, payload)


@router.delete("/admin/accounts/{target_id}")
def delete_account(
    target_id: UUID,
    payload: AccountDelete,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Deletion requires confirmation")
    return AuthService.delete_account(db, current_user, target_id)


@router.post("/admin/accounts", response_model=UserResponse, status_code=201)
def create_account(
    payload: AccountCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return AuthService.register(db, payload)


@router.post("/super-admin/admins", response_model=UserResponse, status_code=201)
def create_admin(
    payload: AccountCreate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return AuthService.register(db, payload, role="admin")


@router.put("/admin/accounts/{target_id}/password")
def reset_password(
    target_id: UUID,
    payload: PasswordReset,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return AuthService.reset_password(db, current_user, target_id, payload.password)


@router.delete("/super-admin/admins/{target_id}")
def disable_admin(
    target_id: UUID,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    target = AuthService.managed_account(db, current_user, target_id)
    if target.role != "admin":
        raise HTTPException(status_code=404, detail="Administrator account not found")
    UserRepository.disable_user(db, target)
    return {"success": True, "disabled": True}



@router.get("/admin/accounts")
def list_accounts(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return UserRepository.list_account_summaries(db, regular_users_only=current_user.role == "admin")


@router.get("/admin/accounts/{target_id}/devices")
def list_account_devices(
    target_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = AuthService.managed_account(db, current_user, target_id)
    if target.role != "user":
        raise HTTPException(status_code=404, detail="Regular user account not found")
    return {
        "user": UserResponse.model_validate(target),
        "devices": [
            {
                "id": device["id"],
                "device_uid": device["device_uid"],
                "device_name": device["device_name"],
                "is_owner": device["is_owner"],
                "assigned": not device["is_owner"],
                "can_control": device["can_control"],
            }
            for device in DeviceService.list_accessible_devices(db, target.id)
        ],
    }
