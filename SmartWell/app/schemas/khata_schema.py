from typing import Optional, List, Literal, Union, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field, condecimal
from uuid import UUID

class KhataCreate(BaseModel):
    customer_name: str = Field(..., min_length=1)
    device_id: str = Field(..., min_length=1)  # device_uid
    price_per_hour: float = Field(default=0.0)
    motor_log_id: Optional[UUID] = None
    cash_received: Optional[float] = Field(default=0.0)
    date: Optional[str] = None
    run_hours: Optional[float] = None
    total_bill: Optional[float] = Field(default=0.0)
    advance_amount: Optional[float] = Field(default=0.0)
    remaining_balance: Optional[float] = None
    payment_status: Optional[Literal["paid", "partial", "unpaid"]] = None

class KhataUpdate(BaseModel):
    customer_name: Optional[str] = None
    run_hours: Optional[float] = None
    price_per_hour: Optional[float] = None
    total_bill: Optional[float] = None
    cash_received: Optional[float] = None
    date: Optional[str] = None
    advance_amount: Optional[float] = None

class KhataResponse(BaseModel):
    id: UUID
    user_id: UUID
    customer_name: str
    device_id: str
    motor_log_id: Optional[UUID] = None
    date: str
    run_hours: float
    price_per_hour: float
    total_bill: float
    cash_received: float
    balance: float
    advance_amount: float = 0.0
    is_cleared: bool
    remaining_balance: Optional[float] = None
    payment_status: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    is_open: bool = False

    class Config:
        from_attributes = True

# Single Customer Rate
class CustomerRateRequest(BaseModel):
    request_id: UUID
    device_id: str = Field(..., min_length=1, max_length=100)
    customer_name: str = Field(..., min_length=1, max_length=100)
    price_per_hour: Union[
        condecimal(ge=0.0, le=99999999.99, max_digits=10, decimal_places=2), str # type: ignore
    ]
    expected_version: Optional[UUID] = None

    class Config:
        extra = "forbid"

# Bulk Rate Update (Preview & Apply)
class CustomerRateBatchRequest(BaseModel):
    request_id: UUID
    device_id: str = Field(..., min_length=1, max_length=100)
    scope: Literal["all", "selected"]
    customers: List[str] = Field(default=[], max_items=10000)
    price_per_hour: Union[
        condecimal(ge=0.0, le=99999999.99, max_digits=10, decimal_places=2), str # type: ignore
    ]
    expected_revision: Optional[str] = Field(None, min_length=64, max_length=64)
    preview_expires_at: Optional[int] = None
    preview_token: Optional[str] = None

    class Config:
        extra = "forbid"

# Safe Payment Processing
class CustomerPaymentRequest(BaseModel):
    request_id: UUID
    device_id: str = Field(..., min_length=1, max_length=100)
    customer_name: str = Field(..., min_length=1, max_length=100)
    from_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    to_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    amount: Union[
        condecimal(gt=0.0, le=99999999.99, max_digits=10, decimal_places=2), str # type: ignore
    ]
    expected_revision: Optional[str] = Field(None, min_length=64, max_length=64)
    preview_expires_at: Optional[int] = None
    preview_token: Optional[str] = None

    class Config:
        extra = "forbid"

class CustomerKhataSummaryResponse(BaseModel):
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    timezone: str = "Asia/Karachi"
    can_edit_rates: bool = True
    totals: Dict[str, Any]
    from_date: str
    to_date: str

class CustomerRosterResponse(BaseModel):
    default_rate: str
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    device_uid: str

class CustomerNameSuggestionsResponse(BaseModel):
    names: List[str]