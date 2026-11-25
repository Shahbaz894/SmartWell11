from typing import Optional, List, Tuple, Dict, Any
from uuid import UUID
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.khata_entry import KhataEntry, KhataPaymentReceipt

class KhataRepository:

    @staticmethod
    def get_by_id(db: Session, entry_id: UUID) -> Optional[KhataEntry]:
        return db.query(KhataEntry).filter(KhataEntry.id == entry_id).first()

    @staticmethod
    def create_entry(db: Session, user_id: UUID, device_uid: str, customer_name: str, run_hours: float, rate: float, date_str: str, motor_log_id: Optional[UUID] = None) -> KhataEntry:
        total_bill = round(run_hours * rate, 2)
        entry = KhataEntry(
            user_id=user_id,
            device_id=device_uid,
            customer_name=customer_name.strip(),
            motor_log_id=motor_log_id,
            date=date_str,
            run_hours=run_hours,
            price_per_hour=rate,
            total_bill=total_bill,
            cash_received=0.0,
            balance=total_bill,
            payment_status="unpaid",
            is_cleared=False
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def get_customer_summary(db: Session, user_id: UUID, device_uid: str, from_date: str, to_date: str, query: str = "", skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        q = db.query(KhataEntry).filter(
            KhataEntry.user_id == user_id,
            KhataEntry.device_id == device_uid,
            KhataEntry.date >= from_date,
            KhataEntry.date <= to_date
        )
        if query:
            q = q.filter(KhataEntry.customer_name.ilike(f"%{query.strip()}%"))

        entries = q.all()

        # Group by customer_name
        groups: Dict[str, Dict[str, Any]] = {}
        total_runtime = 0.0
        total_bill = 0.0
        total_cash = 0.0
        total_balance = 0.0

        for entry in entries:
            c_name = entry.customer_name
            if c_name not in groups:
                groups[c_name] = {
                    "customer_name": c_name,
                    "session_count": 0,
                    "run_hours": 0.0,
                    "total_bill": 0.0,
                    "cash_received": 0.0,
                    "balance": 0.0
                }
            groups[c_name]["session_count"] += 1
            groups[c_name]["run_hours"] += float(entry.run_hours)
            groups[c_name]["total_bill"] += float(entry.total_bill)
            groups[c_name]["cash_received"] += float(entry.cash_received)
            groups[c_name]["balance"] += float(entry.balance)

            total_runtime += float(entry.run_hours)
            total_bill += float(entry.total_bill)
            total_cash += float(entry.cash_received)
            total_balance += float(entry.balance)

        items_list = list(groups.values())
        paginated_items = items_list[skip: skip + limit]

        return {
            "items": paginated_items,
            "total": len(items_list),
            "totals": {
                "customers": len(items_list),
                "run_hours": round(total_runtime, 2),
                "total_bill": round(total_bill, 2),
                "cash_received": round(total_cash, 2),
                "balance": round(total_balance, 2)
            }
        }