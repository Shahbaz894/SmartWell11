from typing import Dict, Any
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.repositories.user_repo import UserRepository
from app.schemas.user_schema import AccountCreate, PasswordChange, UserResponse
from passlib.context import CryptContext
from app.services.jwt_handler import JWTHandler
from app.models.user import User

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:

    @staticmethod
    def register(db: Session, user_in: AccountCreate, *, role: str = "user") -> UserResponse:
        existing = UserRepository.get_by_email(db, user_in.email)
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed_password = password_context.hash(user_in.password)
        try:
            user = UserRepository.create(db, user_in, hashed_password, role=role)
        except IntegrityError:
            db.rollback()
            if UserRepository.get_by_email(db, user_in.email):
                raise HTTPException(status_code=400, detail="Email already registered")
            raise
        return UserResponse.model_validate(user)

    @staticmethod
    def login(db: Session, email: str, password: str) -> Dict[str, Any]:
        user = UserRepository.get_by_email(db, email)
        if not user or not password_context.verify(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account disabled")

        token = JWTHandler.create_token(user)
        return {"access_token": token, "token_type": "bearer", "user": UserResponse.model_validate(user)}

    @staticmethod
    def change_password(db: Session, user_id: UUID, payload: PasswordChange) -> Dict[str, Any]:
        user = UserRepository.get_by_id(db, user_id)
        if not user or not password_context.verify(payload.current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password incorrect")

        hashed = password_context.hash(payload.new_password)
        UserRepository.update_password(db, user, hashed)
        return {"success": True, "reauthenticate": True}

    @staticmethod
    def managed_account(db: Session, actor: User, target_id: UUID) -> User:
        user = UserRepository.get_by_id(db, target_id)
        if not user:
            raise HTTPException(status_code=404, detail="User account not found")

        if (
            user.id == actor.id
            or user.role == "super_admin"
            or (user.role == "admin" and actor.role != "super_admin")
        ):
            raise HTTPException(status_code=403, detail="Account is outside your management scope")

        return user

    @staticmethod
    def reset_password(db: Session, actor: User, target_id: UUID, password: str):
        user = AuthService.managed_account(db, actor, target_id)
        UserRepository.update_password(db, user, password_context.hash(password))
        return {"success": True}

    @staticmethod
    def delete_account(db: Session, actor: User, target_id: UUID) -> Dict[str, Any]:
        user = AuthService.managed_account(db, actor, target_id)
        if UserRepository.has_records(db, target_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "ACCOUNT_HAS_RECORDS", "message": "Account has associated devices or billing records; cannot delete."}
            )

        UserRepository.delete(db, user)
        return {"success": True, "deleted_user_id": str(target_id)}