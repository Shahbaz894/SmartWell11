from typing import Optional, Literal, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID

class ResolutionRequest(BaseModel):
    request_id: UUID
    expected_revision: str = Field(..., min_length=64, max_length=64)
    action: Literal["complete", "cancel"]
    reason: str = Field(..., min_length=3, max_length=2000)
    start_at: Optional[datetime] = None
    stop_at: Optional[datetime] = None
    attest_start: bool = Field(default=False)
    did_not_start: bool = Field(default=False)
    preview_token: Optional[str] = None
    preview_expires_at: Optional[int] = None

    class Config:
        extra = "forbid"

class ResolutionResult(BaseModel):
    start_at: Optional[datetime] = None
    stop_at: Optional[datetime] = None
    start_source: str
    stop_source: str
    duration_hours: float
    ledger_id: Optional[UUID] = None
    ledger_missing: bool = False
    ledger_customer_name: Optional[str] = None
    rate: float
    cash_received: float
    run_hours: float
    total_bill: float
    balance: float
    advance_amount: float
    is_cleared: bool

class ResolutionPreviewResponse(BaseModel):
    result: ResolutionResult
    preview_expires_at: int
    preview_token: str

class ResolutionResponse(BaseModel):
    resolution_id: UUID
    result: ResolutionResult
    idempotent: bool = False

class ResolutionAuditResponse(BaseModel):
    resolution: Optional[Dict[str, Any]] = None
    conflicts: List[Dict[str, Any]] = []