from typing import Optional, List
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.device import Device, device_assignments
from app.models.khata_entry import KhataEntry
from app.schemas.user_schema import AccountCreate, UserResponse

class UserRepository:

    @staticmethod
    def get_by_id(db: Session, user_id: UUID) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
        return db.query(User).offset(skip).limit(limit).all()

    @staticmethod
    def create(db: Session, user_in: AccountCreate, hashed_password: str, *, role: str = "user") -> User:
        user = User(
            name=user_in.name,
            email=user_in.email.lower().strip(),
            hashed_password=hashed_password,
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_password(db: Session, user: User, hashed_password: str) -> User:
        user.hashed_password = hashed_password
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def disable_user(db: Session, user: User) -> User:
        user.is_active = False
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def has_records(db: Session, user_id: UUID) -> bool:
        # Conflict check before account deletion
        device_count = db.query(Device).filter(Device.user_id == user_id).count()
        khata_count = db.query(KhataEntry).filter(KhataEntry.user_id == user_id).count()
        return (device_count > 0 or khata_count > 0)

    @staticmethod
    def delete(db: Session, user: User) -> bool:
        db.delete(user)
        db.commit()
        return True


    @staticmethod
    def list_account_summaries(db: Session, *, regular_users_only: bool):
        owned = select(func.count()).where(Device.user_id == User.id).scalar_subquery()
        assigned = (
            select(func.count())
            .select_from(device_assignments.join(Device, Device.id == device_assignments.c.device_id))
            .where(device_assignments.c.user_id == User.id, Device.user_id != User.id)
            .scalar_subquery()
        )
        query = select(User, owned, assigned).order_by(User.name, User.id)
        if regular_users_only:
            query = query.where(User.role == "user")
        return [
            {
                **UserResponse.model_validate(user).model_dump(),
                "active": user.is_active,
                "owned_device_count": owned_count,
                "assigned_device_count": assigned_count,
                "device_count": owned_count + assigned_count,
            }
            for user, owned_count, assigned_count in db.execute(query)
        ]
