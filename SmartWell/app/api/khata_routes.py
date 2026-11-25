from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.repositories.khata_repo import KhataRepository
from app.repositories.customer_repo import CustomerRepository
from app.schemas.khata_schema import (
    CustomerKhataSummaryResponse,
    CustomerRosterResponse,
    CustomerNameSuggestionsResponse,
    CustomerRateRequest,
    CustomerRateBatchRequest,
    CustomerPaymentRequest,
    KhataCreate,
    KhataUpdate,
    KhataResponse,
)
from app.services.khata_service import KhataService

router = APIRouter(tags=["Khata & Billing"])


# ==========================================
# 1. GROUPED CUSTOMER KHATA & RATE ENDPOINTS
# ==========================================

@router.get("/records/customer-khata", response_model=CustomerKhataSummaryResponse)
def get_customer_khata_summary(
    device_id: str = Query(..., description="ESP32 hardware device_uid"),
    from_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    to_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    q: Optional[str] = Query(""),
    status: Optional[str] = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns grouped customer Khata summary per device and date range in Asia/Karachi time.
    """
    skip = (page - 1) * page_size
    summary = KhataRepository.get_customer_summary(
        db, current_user.id, device_id, from_date, to_date, q or "", skip, page_size
    )
    return {
        "items": summary["items"],
        "total": summary["total"],
        "page": page,
        "page_size": page_size,
        "timezone": "Asia/Karachi",
        "can_edit_rates": True,
        "totals": summary["totals"],
        "from_date": from_date,
        "to_date": to_date,
    }


@router.get("/records/customer-khata/customers", response_model=CustomerRosterResponse)
def get_customer_roster(
    device_id: str = Query(..., description="ESP32 hardware device_uid"),
    q: Optional[str] = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves all known customer names and rates for bulk-rate updates.
    """
    skip = (page - 1) * page_size
    items, total = CustomerRepository.get_roster(db, device_id, q or "", skip, page_size)
    return {
        "default_rate": "150.00",
        "items": [
            {
                "key": c.customer_key,
                "name": c.customer_name,
                "price_per_hour": str(c.price_per_hour),
            }
            for c in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "device_uid": device_id,
    }


@router.get("/records/customer-names", response_model=CustomerNameSuggestionsResponse)
def get_customer_name_suggestions(
    device_id: str = Query(..., description="ESP32 hardware device_uid"),
    prefix: str = Query("", max_length=100),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Provides case-insensitive prefix auto-suggestions for customer inputs.
    """
    names = CustomerRepository.search_names(db, device_id, prefix, limit)
    return {"names": names}


@router.patch("/records/customer-khata/rate")
def update_single_customer_rate(
    request: CustomerRateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Updates the future hourly rate for a single customer.
    """
    return KhataService.update_single_rate(db, request)


@router.post("/records/customer-khata/rates/preview")
def preview_bulk_rates(
    request: CustomerRateBatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Previews bulk rate changes across all or selected customers.
    """
    return KhataService.preview_bulk_rate(db, request)


@router.post("/records/customer-khata/rates/apply")
def apply_bulk_rates(
    request: CustomerRateBatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Applies bulk rate changes using a verified preview_token.
    """
    return KhataService.apply_bulk_rate(db, request)


# ==========================================
# 2. PAYMENT PROCESSING ENDPOINTS
# ==========================================

@router.post("/records/customer-khata/payment/preview")
def preview_customer_payment(
    request: CustomerPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Previews payment allocation across unpaid entries before committing.
    """
    return KhataService.preview_payment(db, request)


@router.post("/records/customer-khata/payment")
def process_customer_payment(
    request: CustomerPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Confirms payment processing using an idempotency request_id and preview_token.
    """
    return KhataService.process_payment(db, request)


@router.get("/records/khata")
def search_khata_ledger(
    device_id: Optional[str] = Query(None),
    q: Optional[str] = Query(""),
    status: Optional[str] = Query("all"),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Performs full-dataset search over per-entry Khata records.
    """
    return KhataService.search_khata_ledger(
        db, current_user.id, device_id, q, status, from_date, to_date, page, page_size
    )


# ==========================================
# 3. LEGACY / PER-ENTRY KHATA COMPATIBILITY
# ==========================================

@router.get("/khata/me")
def get_khata_user_info(current_user: User = Depends(get_current_user)):
    """
    Returns basic user identity for Khata context.
    """
    return {"user_id": str(current_user.id), "email": current_user.email}


@router.get("/khata/", response_model=List[KhataResponse])
def list_all_khata_entries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lists legacy per-entry Khata records.
    """
    return KhataRepository.get_user_entries(db, current_user.id)


@router.post("/khata/", response_model=KhataResponse, status_code=status.HTTP_201_CREATED)
def create_khata_entry(
    payload: KhataCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Creates a new manual Khata entry.
    """
    return KhataRepository.create_manual_entry(db, current_user.id, payload)


@router.get("/khata/{entry_id}", response_model=KhataResponse)
def get_single_khata_entry(
    entry_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Fetches a single Khata entry by UUID.
    """
    return KhataRepository.get_entry_by_id_or_404(db, entry_id, current_user.id)


@router.patch("/khata/{entry_id}", response_model=KhataResponse)
def update_khata_entry(
    entry_id: UUID,
    payload: KhataUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Updates individual fields of a Khata entry.
    """
    return KhataRepository.update_entry(db, entry_id, current_user.id, payload)


@router.delete("/khata/{entry_id}")
def delete_khata_entry(
    entry_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deletes a cleared Khata entry.
    """
    return KhataRepository.delete_entry(db, entry_id, current_user.id)


@router.post("/khata/{entry_id}/payment", response_model=KhataResponse)
def record_khata_entry_payment(
    entry_id: UUID,
    cash_received: float = Query(..., gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Records payment directly against a legacy entry.
    """
    return KhataRepository.record_entry_payment(db, entry_id, current_user.id, cash_received)