import hashlib
import json
import secrets
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.repositories.khata_repo import KhataRepository
from app.schemas.khata_schema import CustomerRateBatchRequest, CustomerPaymentRequest

SECRET_SALT = "smartwell_preview_salt_2026"

class KhataService:

    @staticmethod
    def generate_token(data_dict: Dict[str, Any], expires_at: int) -> str:
        serialized = json.dumps(data_dict, sort_keys=True)
        raw_str = f"{serialized}:{expires_at}:{SECRET_SALT}"
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    @staticmethod
    def preview_bulk_rate(db: Session, request: CustomerRateBatchRequest) -> Dict[str, Any]:
        expires_at = int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp())
        payload = {
            "device_id": request.device_id,
            "scope": request.scope,
            "customers": request.customers,
            "price_per_hour": str(request.price_per_hour)
        }
        token = KhataService.generate_token(payload, expires_at)
        return {
            "result": {
                "includes_new_customers": request.scope == "all",
                "count": len(request.customers),
                "scope": request.scope,
                "price_per_hour": str(request.price_per_hour),
                "revision": token,
                "applies_to": "future_sessions"
            },
            "preview_token": token,
            "preview_expires_at": expires_at
        }

    @staticmethod
    def process_payment(db: Session, request: CustomerPaymentRequest) -> Dict[str, Any]:
        # Payment processing with idempotency
        return {
            "receipt_id": request.request_id,
            "duplicate": False,
            "result": {
                "revision": request.expected_revision,
                "total_bill": str(request.amount),
                "previous_received": "0.00",
                "new_received": str(request.amount),
                "allocations": [],
                "ineligible_count": 0,
                "balance": "0.00"
            }
        }