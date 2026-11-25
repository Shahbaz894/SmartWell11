from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID

class FirmwareReleaseResponse(BaseModel):
    id: UUID
    version: str
    model: str
    size_bytes: int
    sha256: str
    notes: Optional[str] = ""
    target_scope: Literal["selected", "all_model"]
    target_uids: List[str]
    state: Literal["draft", "published", "withdrawn"]
    uploaded_by: UUID
    created_at: datetime
    published_at: Optional[datetime] = None
    url: str

    class Config:
        from_attributes = True

class FirmwareCheckResponse(BaseModel):
    version: str
    model: str
    url: str
    size: int
    sha256: str

class FirmwareConfirm(BaseModel):
    confirm: bool = Field(default=False)