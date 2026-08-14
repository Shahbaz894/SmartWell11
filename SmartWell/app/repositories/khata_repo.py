from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models.khata_entry import KhataEntry
from app.core.logger import logger
from app.core.exceptions import AppException, NotFoundException


def _uuid(value):
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


class KhataRepository:
    def __init__(self, db: Session):
        self.db = db

    def _safe_query(self, operation_name, query_fn):
        try:
            return query_fn()
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error("DB error [%s]: %s", operation_name, repr(exc), exc_info=True)
            raise AppException(500, f"Database error during {operation_name}: {getattr(exc, 'orig', exc)}")

    def create_entry(self, entry: KhataEntry) -> KhataEntry:
        def _run():
            self.db.add(entry)
            self.db.commit()
            self.db.refresh(entry)
            return entry
        return self._safe_query("create_entry", _run)

    def get_entry(self, entry_id, user_id) -> KhataEntry:
        entry = self._safe_query(
            "get_entry",
            lambda: self.db.query(KhataEntry).filter(
                KhataEntry.id == _uuid(entry_id),
                KhataEntry.user_id == _uuid(user_id),
            ).first(),
        )
        if entry is None:
            raise NotFoundException(f"Khata entry not found: {entry_id}")
        return entry

    def get_all_entries(self, user_id) -> list[KhataEntry]:
        return self._safe_query(
            "get_all_entries",
            lambda: self.db.query(KhataEntry)
                .filter(KhataEntry.user_id == _uuid(user_id))
                .order_by(KhataEntry.created_at.desc())
                .all(),
        )

    def save(self, entry: KhataEntry) -> KhataEntry:
        def _run():
            self.db.commit()
            self.db.refresh(entry)
            return entry
        return self._safe_query("save", _run)

    def update_entry(self, entry: KhataEntry, data: dict) -> KhataEntry:
        for key, value in data.items():
            if hasattr(entry, key) and value is not None:
                setattr(entry, key, value)
        return self.save(entry)

    def delete_entry(self, entry: KhataEntry) -> bool:
        def _run():
            self.db.delete(entry)
            self.db.commit()
            return True
        return self._safe_query("delete_entry", _run)
