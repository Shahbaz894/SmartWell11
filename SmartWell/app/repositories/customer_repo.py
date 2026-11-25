from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from app.models.customer import Customer, CustomerRate

class CustomerRepository:

    @staticmethod
    def get_or_create_customer(db: Session, device_uid: str, customer_name: str) -> Customer:
        key = customer_name.strip().lower()
        customer = db.query(Customer).filter(
            Customer.device_uid == device_uid,
            Customer.customer_key == key
        ).first()

        if not customer:
            customer = Customer(
                device_uid=device_uid,
                customer_key=key,
                customer_name=customer_name.strip()
            )
            db.add(customer)
            db.commit()
            db.refresh(customer)
        return customer

    @staticmethod
    def get_rate(db: Session, device_uid: str, customer_name: str) -> Optional[CustomerRate]:
        key = customer_name.strip().lower()
        return db.query(CustomerRate).filter(
            CustomerRate.device_uid == device_uid,
            CustomerRate.customer_key == key
        ).first()

    @staticmethod
    def search_names(db: Session, device_uid: str, prefix: str, limit: int = 20) -> List[str]:
        if not prefix:
            return []
        prefix_key = prefix.strip().lower()
        customers = db.query(Customer.customer_name).filter(
            Customer.device_uid == device_uid,
            Customer.customer_key.startswith(prefix_key)
        ).order_by(Customer.customer_name.asc()).limit(min(limit, 50)).all()
        return [c for c in customers]

    @staticmethod
    def get_roster(db: Session, device_uid: str, query: str = "", skip: int = 0, limit: int = 100) -> Tuple[List[CustomerRate], int]:
        q = db.query(CustomerRate).filter(CustomerRate.device_uid == device_uid)
        if query:
            q = q.filter(CustomerRate.customer_key.contains(query.strip().lower()))

        total = q.count()
        items = q.order_by(CustomerRate.customer_name.asc()).offset(skip).limit(limit).all()
        return items, total