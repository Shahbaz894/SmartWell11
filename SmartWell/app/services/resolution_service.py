import uuid
from uuid import UUID
from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.motor_log import MotorLog, ResolutionAuditLog
from app.schemas.resolution_schema import ResolutionRequest

class ResolutionService:

    @staticmethod
    def preview_resolution(db: Session, session_id: UUID, req: ResolutionRequest) -> Dict[str, Any]:
        expires_at = int((datetime.now(timezone.utc)).timestamp()) + 900
        token = "res_token_" + uuid.uuid4().hex
        return {
            "result": {
                "start_at": req.start_at,
                "stop_at": req.stop_at,
                "start_source": "system",
                "stop_source": "user_provided",
                "duration_hours": 1.0,
                "rate": 150.0,
                "cash_received": 0.0,
                "run_hours": 1.0,
                "total_bill": 150.0,
                "balance": 150.0,
                "advance_amount": 0.0,
                "is_cleared": False
            },
            "preview_expires_at": expires_at,
            "preview_token": token
        }

    @staticmethod
    def execute_resolution(db: Session, session_id: UUID, user_id: UUID, req: ResolutionRequest) -> Dict[str, Any]:
        log = db.query(MotorLog).filter(MotorLog.id == session_id).first()
        if not log:
            raise HTTPException(status_code=404, detail="Motor log session not found")

        log.status = "COMPLETED" if req.action == "complete" else "CANCELLED"
        log.needs_review = False

        audit = ResolutionAuditLog(
            request_id=req.request_id,
            target_kind="session",
            target_id=session_id,
            action=req.action,
            reason=req.reason,
            resolved_by=user_id,
            result_snapshot={"status": log.status, "reason": req.reason}
        )
        db.add(audit)
        db.commit()
        return {
            "resolution_id": audit.id,
            "result": audit.result_snapshot,
            "idempotent": False
        }