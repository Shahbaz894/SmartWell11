from typing import List, Dict, Any
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import and_, delete, insert, or_, select, update
from sqlalchemy.orm import Session

from app.models.device import Device, device_assignments
from app.models.user import User
from app.repositories.device_repo import DeviceRepository
from app.schemas.device_schema import DeviceCreate, DeviceResponse, DeviceUpdate, TransferOwnership

class DeviceService:

    @staticmethod
    def register_device(db: Session, owner_id: UUID, device_in: DeviceCreate):
        owner = db.get(User, owner_id)
        if owner is None or not owner.is_active:
            raise HTTPException(status_code=404, detail="Active owner account not found")
        repo = DeviceRepository(db)
        if repo.get_by_uid(device_in.device_uid):
            raise HTTPException(status_code=400, detail="Device UID already provisioned")
        return repo.create_device(Device(user_id=owner_id, **device_in.model_dump()))

    @staticmethod
    def list_accessible_devices(db: Session, user_id: UUID) -> List[Dict[str, Any]]:
        query = (
            select(Device, device_assignments.c.can_control)
            .outerjoin(
                device_assignments,
                and_(device_assignments.c.device_id == Device.id, device_assignments.c.user_id == user_id),
            )
            .where(or_(Device.user_id == user_id, device_assignments.c.user_id == user_id))
            .order_by(Device.created_at.desc(), Device.id)
        )
        return [
            {
                **DeviceResponse.model_validate(device).model_dump(),
                "is_owner": device.user_id == user_id,
                "can_control": device.user_id == user_id or bool(can_control),
            }
            for device, can_control in db.execute(query)
        ]

    @staticmethod
    def update_device(db: Session, device_id: UUID, owner_id: UUID, payload: DeviceUpdate):
        repo = DeviceRepository(db)
        device = repo.get_by_id(device_id)
        if device is None or device.user_id != owner_id:
            raise HTTPException(status_code=404, detail="Device not found for this owner")
        for name, value in payload.model_dump(exclude_unset=True).items():
            if name == "device_name" and value is None:
                raise HTTPException(status_code=422, detail="Device name cannot be null")
            setattr(device, name, value)
        return repo.update_device(device)

    @staticmethod
    def get_assignments(db: Session, device_id: UUID):
        device = db.get(Device, device_id)
        if device is None:
            raise HTTPException(status_code=404, detail="Device not found")
        query = (
            select(User.id.label("user_id"), User.name, User.email, device_assignments.c.can_control)
            .join(device_assignments, device_assignments.c.user_id == User.id)
            .where(device_assignments.c.device_id == device_id)
            .order_by(User.name, User.id)
        )
        return {"owner_id": device.user_id, "assignments": [dict(row) for row in db.execute(query).mappings()]}

    @staticmethod
    def grant_assignment(db: Session, device_id: UUID, target_user_id: UUID, can_control: bool):
        device = db.get(Device, device_id, with_for_update=True)
        target = db.get(User, target_user_id)
        if device is None or target is None or not target.is_active or target.role != "user":
            raise HTTPException(status_code=404, detail="Device or active regular user not found")
        if device.user_id == target_user_id:
            raise HTTPException(status_code=409, detail="Device owner already has control")
        assignment = and_(
            device_assignments.c.device_id == device_id,
            device_assignments.c.user_id == target_user_id,
        )
        changed = db.execute(update(device_assignments).where(assignment).values(can_control=can_control))
        if not changed.rowcount:
            db.execute(insert(device_assignments).values(
                device_id=device_id, user_id=target_user_id, can_control=can_control,
            ))
        db.commit()
        return {"success": True}

    @staticmethod
    def revoke_assignment(db: Session, device_id: UUID, target_user_id: UUID):
        if db.get(Device, device_id, with_for_update=True) is None:
            raise HTTPException(status_code=404, detail="Device not found")
        db.execute(delete(device_assignments).where(
            device_assignments.c.device_id == device_id,
            device_assignments.c.user_id == target_user_id,
        ))
        db.commit()
        return {"success": True}

    @staticmethod
    def transfer_ownership(db: Session, device_id: UUID, payload: TransferOwnership):
        if not payload.confirm:
            raise HTTPException(status_code=400, detail="Explicit confirm: true required for ownership transfer")
        device = DeviceRepository(db).get_by_id(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        DeviceRepository.transfer_ownership(db, device, payload.new_owner_id)
        return {
            "success": True,
            "owner_id": payload.new_owner_id,
            "history_policy": "Existing Khata remains with its original account"
        }