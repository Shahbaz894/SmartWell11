# # from uuid import UUID, uuid4
# # from datetime import datetime

# # from sqlalchemy.exc import SQLAlchemyError, IntegrityError

# # from app.models.device import Device
# # from app.models.motor_log import MotorLog
# # from app.repositories.khata_repo import KhataRepository
# # from app.models.khata_entry import KhataEntry
# # from app.core.logger import logger
# # from app.core.exceptions import AppException, NotFoundException


# # def _db_error(exc: Exception) -> str:
# #     """
# #     Return the real database error message.

# #     SQLAlchemy wraps PostgreSQL errors.
# #     exc.orig usually contains the actual PostgreSQL error.
# #     """
# #     return str(exc.orig) if hasattr(exc, "orig") else str(exc)


# # def _log_db_exception(operation: str, exc: Exception, **context) -> None:
# #     """
# #     Log maximum useful SQLAlchemy/PostgreSQL diagnostic information.

# #     This is intentionally defensive because not every exception exposes
# #     statement/params/orig attributes.
# #     """
# #     details = {
# #         "operation": operation,
# #         "error_type": type(exc).__name__,
# #         "error": str(exc),
# #         "db_error": _db_error(exc),
# #     }

# #     statement = getattr(exc, "statement", None)
# #     params = getattr(exc, "params", None)

# #     if statement:
# #         details["sql_statement"] = statement

# #     if params:
# #         details["sql_params"] = params

# #     details.update(context)

# #     logger.error(
# #         "DATABASE FAILURE: %s",
# #         " | ".join(f"{key}={value}" for key, value in details.items()),
# #         exc_info=True,
# #     )


# # def _to_float(value) -> float:
# #     """
# #     Convert Decimal, int, float, string number, or None to float.

# #     PostgreSQL Numeric columns often return Decimal.
# #     This avoids Decimal and float arithmetic errors.
# #     """
# #     if value is None:
# #         return 0.0

# #     try:
# #         return float(value)
# #     except (TypeError, ValueError) as exc:
# #         logger.error(
# #             "Numeric conversion failed: value=%s error_type=%s error=%s",
# #             value,
# #             type(exc).__name__,
# #             str(exc),
# #             exc_info=True,
# #         )
# #         raise AppException(
# #             status_code=400,
# #             detail=f"Invalid numeric value '{value}'",
# #         )


# # # Detailed flow logs use INFO so they are visible with a normal production
# # # logger configuration. SQLAlchemy debug details use ERROR with exc_info=True
# # # when a database operation fails.
# # class KhataService:
# #     """
# #     Service layer for Khata ledger entries.

# #     MQTT note:
# #     - This service does not publish or subscribe MQTT.
# #     - ESP32 sends telemetry by MQTT.
# #     - Motor start and stop commands use MQTT through MotorService.
# #     - Khata uses saved PostgreSQL data such as Device and MotorLog.

# #     Responsibilities:
# #     - Validate device ownership.
# #     - Calculate bill from run hours and price per hour.
# #     - Create ledger entries.
# #     - Update ledger entries.
# #     - Record partial or full payments.
# #     - Delete only fully cleared entries.
# #     """

# #     def __init__(self, db):
# #         self.db = db
# #         self.repo = KhataRepository(db)

# #     @staticmethod
# #     def _compute_payment_status(balance: float, cash: float) -> str:
# #         """
# #         Compute payment status from balance and cash received.

# #         Returns:
# #             paid, partial, or unpaid
# #         """
# #         if balance <= 0:
# #             return "paid"
# #         if cash > 0:
# #             return "partial"
# #         return "unpaid"

# #     @staticmethod
# #     def _attach_computed_fields(entry: KhataEntry) -> KhataEntry:

# #         balance = _to_float(entry.balance)
# #         cash = _to_float(entry.cash_received)

# #         logger.debug(
# #             "Khata computed fields: entry_id=%s balance=%s cash_received=%s",
# #             getattr(entry, "id", None),
# #             balance,
# #             cash,
# #         )

# #         entry.remaining_balance = balance

# #         entry.payment_status = (
# #             KhataService._compute_payment_status(
# #                 balance,
# #                 cash,
# #             )
# #         )

# #         entry.advance_amount = _to_float(
# #             getattr(entry, "advance_amount", 0)
# #         )

# #         return entry

# #     def _get_owned_device(self, user_id: UUID, device_id: str) -> Device:
# #         """
# #         Get a device owned by the user.

# #         Accepts both:
# #         - device_uid, for example ESP32_001_TW
# #         - internal UUID devices.id

# #         Returns:
# #             Device ORM object.

# #         Raises:
# #             AppException if device does not exist or does not belong to user.
# #         """
# #         logger.info(
# #             "Khata device lookup START: user_id=%s requested_device_id=%s",
# #             user_id,
# #             device_id,
# #         )

# #         try:
# #             logger.info(
# #                 "Khata device lookup STEP 1: searching Device.device_uid=%s",
# #                 device_id,
# #             )
# #             device = (
# #                 self.db.query(Device)
# #                 .filter(Device.device_uid == device_id, Device.user_id == user_id)
# #                 .first()
# #             )

# #             logger.info(
# #                 "Khata device lookup STEP 1 RESULT: found=%s device_pk=%s device_uid=%s",
# #                 bool(device),
# #                 getattr(device, "id", None),
# #                 getattr(device, "device_uid", None),
# #             )

# #             if not device:
# #                 logger.info(
# #                     "Khata device lookup STEP 2: searching Device.id=%s",
# #                     device_id,
# #                 )
# #                 device = (
# #                     self.db.query(Device)
# #                     .filter(Device.id == device_id, Device.user_id == user_id)
# #                     .first()
# #                 )

# #                 logger.info(
# #                     "Khata device lookup STEP 2 RESULT: found=%s device_pk=%s device_uid=%s",
# #                     bool(device),
# #                     getattr(device, "id", None),
# #                     getattr(device, "device_uid", None),
# #                 )

# #         except SQLAlchemyError as exc:
# #             _log_db_exception(
# #                 "Khata device ownership lookup",
# #                 exc,
# #                 user_id=user_id,
# #                 requested_device_id=device_id,
# #             )
# #             raise AppException(
# #                 status_code=500,
# #                 detail=f"Database error while looking up device: {_db_error(exc)}",
# #             )

# #         if not device:
# #             logger.warning(
# #                 "Khata device lookup denied. Device not found or not owned: user_id=%s device_id=%s",
# #                 user_id,
# #                 device_id,
# #             )
# #             raise AppException(
# #                 status_code=404,
# #                 detail="Device not found or does not belong to you",
# #             )

# #         return device
# #     def create_entry(self, user_id: UUID, data: dict) -> KhataEntry:
        
                
# #         """
# #         Create a Khata ledger entry.

# #         ```
# #         Supports:
# #         - run_hours directly
# #         - motor_log_id based billing
# #         - partial payment
# #         - full payment
# #         - advance payment
# #         """

# #         try:
# #             logger.info(
# #                 "Khata create START: user_id=%s customer=%s device_id=%s motor_log_id=%s "
# #                 "run_hours=%s price_per_hour=%s cash_received=%s date=%s",
# #                 user_id,
# #                 data.get("customer_name"),
# #                 data.get("device_id"),
# #                 data.get("motor_log_id"),
# #                 data.get("run_hours"),
# #                 data.get("price_per_hour"),
# #                 data.get("cash_received"),
# #                 data.get("date"),
# #             )

# #             # ---------------------------------------------------------
# #             # Validate Device
# #             # ---------------------------------------------------------
# #             device_id = data.get("device_id")

# #             if not device_id:
# #                 raise AppException(
# #                     status_code=400,
# #                     detail="device_id is required",
# #                 )

# #             logger.info(
# #                 "Khata create STEP device validation: user_id=%s device_id=%s",
# #                 user_id,
# #                 device_id,
# #             )

# #             device = self._get_owned_device(
# #                 user_id=user_id,
# #                 device_id=device_id,
# #             )

# #             logger.info(
# #                 "Khata create STEP device validated: db_device_pk=%s db_device_uid=%s",
# #                 getattr(device, "id", None),
# #                 getattr(device, "device_uid", None),
# #             )

# #             # KhataEntry.device_id is a public device UID string.
# #             db_device_id = device.device_uid
# #             data["device_id"] = db_device_id

# #             # ---------------------------------------------------------
# #             # Default Date
# #             # ---------------------------------------------------------
# #             if not data.get("date"):
# #                 data["date"] = datetime.now().date()

# #             # ---------------------------------------------------------
# #             # Motor Log Billing
# #             # ---------------------------------------------------------
# #             if data.get("motor_log_id"):

# #                 logger.info(
# #                     "Khata create STEP motor log lookup START: motor_log_id=%s device_id=%s",
# #                     data.get("motor_log_id"),
# #                     db_device_id,
# #                 )

# #                 try:
# #                     motor_log_id = int(data["motor_log_id"])
# #                 except (TypeError, ValueError) as exc:
# #                     logger.error(
# #                         "Khata motor_log_id conversion failed: value=%s type=%s error=%s",
# #                         data.get("motor_log_id"),
# #                         type(data.get("motor_log_id")).__name__,
# #                         str(exc),
# #                         exc_info=True,
# #                     )
# #                     raise AppException(
# #                         status_code=400,
# #                         detail="motor_log_id must be a valid integer",
# #                     )

# #                 try:
# #                     log = (
# #                         self.db.query(MotorLog)
# #                         .filter(
# #                             MotorLog.id == motor_log_id,
# #                             MotorLog.device_id == db_device_id,
# #                         )
# #                         .first()
# #                     )

# #                     logger.info(
# #                         "Khata create STEP motor log lookup RESULT: found=%s "
# #                         "id=%s device_id=%s start_time=%s end_time=%s",
# #                         bool(log),
# #                         getattr(log, "id", None),
# #                         getattr(log, "device_id", None),
# #                         getattr(log, "start_time", None),
# #                         getattr(log, "end_time", None),
# #                     )
# #                 except SQLAlchemyError as exc:
# #                     _log_db_exception(
# #                         "Khata motor log lookup",
# #                         exc,
# #                         user_id=user_id,
# #                         motor_log_id=motor_log_id,
# #                         device_id=db_device_id,
# #                     )
# #                     raise AppException(
# #                         status_code=500,
# #                         detail=f"Database error while reading motor log: {_db_error(exc)}",
# #                     )

# #                 if not log:
# #                     raise AppException(
# #                         status_code=404,
# #                         detail="Motor log not found for this device",
# #                     )

# #                 if not log.start_time or not log.end_time:
# #                     raise AppException(
# #                         status_code=400,
# #                         detail="Motor log is incomplete. Motor may still be running.",
# #                     )

# #                 run_seconds = (
# #                     log.end_time - log.start_time
# #                 ).total_seconds()

# #                 data["run_hours"] = round(
# #                     run_seconds / 3600,
# #                     2,
# #                 )

# #                 logger.info(
# #                     "Khata motor billing calculation: motor_log_id=%s start=%s end=%s "
# #                     "run_seconds=%s run_hours=%s",
# #                     motor_log_id,
# #                     log.start_time,
# #                     log.end_time,
# #                     run_seconds,
# #                     data["run_hours"],
# #                 )

# #                 logger.info(
# #                     "Khata run_hours calculated from motor log: motor_log_id=%s run_hours=%s",
# #                     data["motor_log_id"],
# #                     data["run_hours"],
# #                 )

# #             # ---------------------------------------------------------
# #             # Validation
# #             # ---------------------------------------------------------
# #             if not data.get("run_hours"):
# #                 raise AppException(
# #                     status_code=400,
# #                     detail="run_hours is required. Supply it directly or provide motor_log_id.",
# #                 )

# #             if data.get("price_per_hour") is None:
# #                 raise AppException(
# #                     status_code=400,
# #                     detail="price_per_hour is required",
# #                 )

# #             run_hours = round(
# #                 _to_float(data["run_hours"]),
# #                 2,
# #             )

# #             price_per_hour = round(
# #                 _to_float(data["price_per_hour"]),
# #                 2,
# #             )

# #             cash_received = round(
# #                 _to_float(data.get("cash_received")),
# #                 2,
# #             )

# #             if run_hours <= 0:
# #                 raise AppException(
# #                     status_code=400,
# #                     detail="run_hours must be greater than 0",
# #                 )

# #             if price_per_hour < 0:
# #                 raise AppException(
# #                     status_code=400,
# #                     detail="price_per_hour cannot be negative",
# #                 )

# #             if cash_received < 0:
# #                 raise AppException(
# #                     status_code=400,
# #                     detail="cash_received cannot be negative",
# #                 )

# #             # ---------------------------------------------------------
# #             # Bill Calculation
# #             # ---------------------------------------------------------
# #             total_bill = round(
# #                 run_hours * price_per_hour,
# #                 2,
# #             )

# #             logger.info(
# #                 "Khata billing calculation: run_hours=%s price_per_hour=%s "
# #                 "total_bill=%s cash_received=%s",
# #                 run_hours,
# #                 price_per_hour,
# #                 total_bill,
# #                 cash_received,
# #             )

# #             if cash_received >= total_bill:

# #                 advance_amount = round(
# #                     cash_received - total_bill,
# #                     2,
# #                 )

# #                 balance = 0
# #                 is_cleared = True

# #             else:

# #                 advance_amount = 0

# #                 balance = round(
# #                     total_bill - cash_received,
# #                     2,
# #                 )

# #                 is_cleared = False

# #             # ---------------------------------------------------------
# #             # Save Values
# #             # ---------------------------------------------------------
# #             data.update(
# #                 run_hours=run_hours,
# #                 price_per_hour=price_per_hour,
# #                 total_bill=total_bill,
# #                 cash_received=cash_received,
# #                 balance=balance,
# #                 advance_amount=advance_amount,
# #                 is_cleared=is_cleared,
# #             )

# #             # Remove client-controlled fields
# #             for field in (
# #                 "remaining_balance",
# #                 "payment_status",
# #                 "user_id",
# #             ):
# #                 data.pop(field, None)

# #             # ---------------------------------------------------------
# #             # Create Entry
# #             # ---------------------------------------------------------
# #             logger.info(
# #                 "Khata ORM object creation: user_id=%s device_id=%s data_keys=%s "
# #                 "total_bill=%s balance=%s cash_received=%s is_cleared=%s",
# #                 user_id,
# #                 db_device_id,
# #                 list(data.keys()),
# #                 data.get("total_bill"),
# #                 data.get("balance"),
# #                 data.get("cash_received"),
# #                 data.get("is_cleared"),
# #             )

# #             entry = KhataEntry(
# #                 user_id=user_id,
# #                 **data,
# #             )

# #             logger.info("Khata repository create START: user_id=%s", user_id)
# #             created = self.repo.create_entry(entry)
# #             logger.info(
# #                 "Khata repository create SUCCESS: id=%s",
# #                 getattr(created, "id", None),
# #             )

# #             logger.info(
# #                 "Khata entry created: id=%s user_id=%s device_id=%s total_bill=%s cash=%s balance=%s advance=%s",
# #                 created.id,
# #                 user_id,
# #                 db_device_id,
# #                 created.total_bill,
# #                 created.cash_received,
# #                 created.balance,
# #                 created.advance_amount,
# #             )

# #             return self._attach_computed_fields(created)

# #         except AppException:
# #             raise

# #         except IntegrityError as exc:
# #             _log_db_exception(
# #                 "Khata create integrity error",
# #                 exc,
# #                 user_id=user_id,
# #                 device_id=data.get("device_id"),
# #                 motor_log_id=data.get("motor_log_id"),
# #                 data_keys=list(data.keys()),
# #             )

# #             raise AppException(
# #                 status_code=400,
# #                 detail=f"Khata create failed. DB error: {_db_error(exc)}",
# #             )

# #         except SQLAlchemyError as exc:
# #             _log_db_exception(
# #                 "Khata create database error",
# #                 exc,
# #                 user_id=user_id,
# #                 device_id=data.get("device_id"),
# #                 motor_log_id=data.get("motor_log_id"),
# #                 data_keys=list(data.keys()),
# #             )

# #             raise AppException(
# #                 status_code=500,
# #                 detail=f"Database error while creating Khata entry: {_db_error(exc)}",
# #             )

# #         except Exception as exc:
# #             logger.error(
# #                 "Khata create unexpected error: user_id=%s error_type=%s error=%s",
# #                 user_id,
# #                 type(exc).__name__,
# #                 str(exc),
# #                 exc_info=True,
# #             )

# #             raise AppException(
# #                 status_code=500,
# #                 detail=f"Unexpected error while creating Khata entry: {type(exc).__name__}: {str(exc)}",
# #             )
        

# #     def get_all_entries(self, user_id: UUID) -> list[KhataEntry]:
# #         """
# #         Return all Khata entries owned by one user.
# #         """
# #         try:
# #             logger.info(
# #                 "Khata get_all START: user_id=%s repo=%s db=%s",
# #                 user_id,
# #                 type(self.repo).__name__,
# #                 type(self.db).__name__,
# #             )

# #             logger.info(
# #                 "Khata get_all repository query START: user_id=%s",
# #                 user_id,
# #             )

# #             entries = self.repo.get_all_entries(user_id)

# #             logger.info(
# #                 "Khata get_all repository query SUCCESS: user_id=%s count=%s",
# #                 user_id,
# #                 len(entries),
# #             )

# #             for index, entry in enumerate(entries):
# #                 logger.debug(
# #                     "Khata get_all entry[%s]: id=%s device_id=%s customer=%s "
# #                     "run_hours=%s price_per_hour=%s total_bill=%s cash_received=%s "
# #                     "balance=%s is_cleared=%s",
# #                     index,
# #                     getattr(entry, "id", None),
# #                     getattr(entry, "device_id", None),
# #                     getattr(entry, "customer_name", None),
# #                     getattr(entry, "run_hours", None),
# #                     getattr(entry, "price_per_hour", None),
# #                     getattr(entry, "total_bill", None),
# #                     getattr(entry, "cash_received", None),
# #                     getattr(entry, "balance", None),
# #                     getattr(entry, "is_cleared", None),
# #                 )
# #                 self._attach_computed_fields(entry)

# #             logger.info(
# #                 "Khata get_all SUCCESS: user_id=%s count=%s",
# #                 user_id,
# #                 len(entries),
# #             )

# #             return entries

# #         except AppException:
# #             raise

# #         except SQLAlchemyError as exc:
# #             _log_db_exception(
# #                 "Khata get_all database error",
# #                 exc,
# #                 user_id=user_id,
# #             )
# #             raise AppException(
# #                 status_code=500,
# #                 detail=f"Database error while fetching Khata entries: {_db_error(exc)}",
# #             )

# #         except Exception as exc:
# #             logger.error(
# #                 "Khata fetch all unexpected error: user_id=%s error_type=%s error=%s",
# #                 user_id,
# #                 type(exc).__name__,
# #                 str(exc),
# #                 exc_info=True,
# #             )
# #             raise AppException(
# #                 status_code=500,
# #                 detail=f"Unexpected error while fetching Khata entries: {type(exc).__name__}: {str(exc)}",
# #             )

# #     def get_entry(self, entry_id: str, user_id: UUID) -> KhataEntry:
# #         """
# #         Return one Khata entry and enforce user ownership.
# #         """
# #         try:
# #             entry = self.repo.get_entry(entry_id=entry_id, user_id=user_id)

# #             logger.info(
# #                 "Khata entry fetched: entry_id=%s user_id=%s",
# #                 entry_id,
# #                 user_id,
# #             )

# #             return self._attach_computed_fields(entry)

# #         except NotFoundException:
# #             logger.warning(
# #                 "Khata entry not found: entry_id=%s user_id=%s",
# #                 entry_id,
# #                 user_id,
# #             )
# #             raise AppException(
# #                 status_code=404,
# #                 detail="Khata entry not found",
# #             )

# #         except AppException:
# #             raise

# #         except SQLAlchemyError as exc:
# #             _log_db_exception(
# #                 "Khata get database error",
# #                 exc,
# #                 entry_id=entry_id,
# #                 user_id=user_id,
# #             )
# #             raise AppException(
# #                 status_code=500,
# #                 detail=f"Database error while fetching Khata entry: {_db_error(exc)}",
# #             )

# #         except Exception as exc:
# #             logger.error(
# #                 "Khata get unexpected error: entry_id=%s user_id=%s error_type=%s error=%s",
# #                 entry_id,
# #                 user_id,
# #                 type(exc).__name__,
# #                 str(exc),
# #                 exc_info=True,
# #             )
# #             raise AppException(
# #                 status_code=500,
# #                 detail=f"Unexpected error while fetching Khata entry: {type(exc).__name__}: {str(exc)}",
# #             )

# #     def update_entry(
# #         self,
# #         entry_id: str,
# #         user_id: UUID,
# #         data: dict,
# #     ) -> KhataEntry:
# #         try:
# #             logger.info(
# #                 "Khata update requested: entry_id=%s user_id=%s",
# #                 entry_id,
# #                 user_id,
# #             )

# #             logger.info(
# #                 "Khata update repository lookup START: entry_id=%s user_id=%s",
# #                 entry_id,
# #                 user_id,
# #             )

# #             entry = self.repo.get_entry(
# #                 entry_id=entry_id,
# #                 user_id=user_id,
# #             )

# #             logger.info(
# #                 "Khata update repository lookup SUCCESS: entry_id=%s current_device=%s "
# #                 "current_total_bill=%s current_cash=%s current_balance=%s",
# #                 entry_id,
# #                 getattr(entry, "device_id", None),
# #                 getattr(entry, "total_bill", None),
# #                 getattr(entry, "cash_received", None),
# #                 getattr(entry, "balance", None),
# #             )

# #             clean_data = {k: v for k, v in data.items() if v is not None}

# #             logger.info(
# #                 "Khata update clean payload: entry_id=%s fields=%s",
# #                 entry_id,
# #                 list(clean_data.keys()),
# #             )

# #             if "run_hours" in clean_data:
# #                 clean_data["run_hours"] = round(_to_float(clean_data["run_hours"]), 2)
# #             if "price_per_hour" in clean_data:
# #                 clean_data["price_per_hour"] = round(_to_float(clean_data["price_per_hour"]), 2)
# #             if "cash_received" in clean_data:
# #                 clean_data["cash_received"] = round(_to_float(clean_data["cash_received"]), 2)

# #             logger.info(
# #                 "Khata update repository write #1 START: entry_id=%s",
# #                 entry_id,
# #             )
# #             updated = self.repo.update_entry(entry, clean_data)

# #             logger.info(
# #                 "Khata update repository write #1 SUCCESS: entry_id=%s",
# #                 entry_id,
# #             )

# #             run_hours = _to_float(updated.run_hours)
# #             price_per_hour = _to_float(updated.price_per_hour)
# #             cash_received = _to_float(updated.cash_received)

# #             total_bill = round(run_hours * price_per_hour, 2)

# #             if cash_received >= total_bill:
# #                 advance_amount = round(cash_received - total_bill, 2)
# #                 balance = 0
# #                 is_cleared = True
# #             else:
# #                 advance_amount = 0
# #                 balance = round(total_bill - cash_received, 2)
# #                 is_cleared = False

# #             logger.info(
# #                 "Khata update recalculation: entry_id=%s run_hours=%s price_per_hour=%s "
# #                 "cash_received=%s total_bill=%s balance=%s advance=%s is_cleared=%s",
# #                 entry_id,
# #                 run_hours,
# #                 price_per_hour,
# #                 cash_received,
# #                 total_bill,
# #                 balance,
# #                 advance_amount,
# #                 is_cleared,
# #             )

# #             updated = self.repo.update_entry(
# #                 updated,
# #                 {
# #                     "total_bill": total_bill,
# #                     "balance": balance,
# #                     "advance_amount": advance_amount,
# #                     "is_cleared": is_cleared,
# #                 },
# #             )

# #             logger.info(
# #                 "Khata update SUCCESS: entry_id=%s",
# #                 entry_id,
# #             )

# #             return self._attach_computed_fields(updated)

# #         except NotFoundException:
# #             raise AppException(status_code=404, detail="Khata entry not found")
        
# #         except AppException:
# #             raise

# #         except SQLAlchemyError as exc:
# #             _log_db_exception(
# #                 "Khata update database error",
# #                 exc,
# #                 entry_id=entry_id,
# #                 user_id=user_id,
# #             )
# #             raise AppException(
# #                 status_code=500,
# #                 detail=f"Database error while updating Khata entry: {_db_error(exc)}",
# #             )

# #         except Exception as exc:
# #             logger.error(
# #                 "Khata update unexpected error: entry_id=%s user_id=%s error_type=%s error=%s",
# #                 entry_id, user_id, type(exc).__name__, str(exc), exc_info=True,
# #             )
# #             raise AppException(
# #                 status_code=500,
# #                 detail=f"Unexpected error while updating Khata entry: {type(exc).__name__}: {str(exc)}",
# #             )

# #     def update_payment(
# #         self,
# #         entry_id: str,
# #         user_id: UUID,
# #         cash_received: float,
# #     ) -> KhataEntry:
# #         try:
# #             if cash_received <= 0:
# #                 raise AppException(status_code=400, detail="cash_received must be greater than 0")

# #             logger.info(
# #                 "Khata payment repository lookup START: entry_id=%s user_id=%s cash_received=%s",
# #                 entry_id,
# #                 user_id,
# #                 cash_received,
# #             )

# #             entry = self.repo.get_entry(entry_id=entry_id, user_id=user_id)

# #             logger.info(
# #                 "Khata payment repository lookup SUCCESS: entry_id=%s current_cash=%s "
# #                 "total_bill=%s balance=%s",
# #                 entry_id,
# #                 getattr(entry, "cash_received", None),
# #                 getattr(entry, "total_bill", None),
# #                 getattr(entry, "balance", None),
# #             )

# #             current_cash = _to_float(entry.cash_received)
# #             total_cash = round(current_cash + cash_received, 2)
# #             total_bill = _to_float(entry.total_bill)

# #             if total_cash >= total_bill:
# #                 advance_amount = round(total_cash - total_bill, 2)
# #                 balance = 0
# #                 is_cleared = True
# #             else:
# #                 advance_amount = 0
# #                 balance = round(total_bill - total_cash, 2)
# #                 is_cleared = False

# #             logger.info(
# #                 "Khata payment calculation: entry_id=%s current_cash=%s new_payment=%s "
# #                 "total_cash=%s total_bill=%s balance=%s advance=%s is_cleared=%s",
# #                 entry_id,
# #                 current_cash,
# #                 cash_received,
# #                 total_cash,
# #                 total_bill,
# #                 balance,
# #                 advance_amount,
# #                 is_cleared,
# #             )

# #             updated = self.repo.update_entry(
# #                 entry,
# #                 {
# #                     "cash_received": total_cash,
# #                     "balance": balance,
# #                     "advance_amount": advance_amount,
# #                     "is_cleared": is_cleared,
# #                 },
# #             )

# #             logger.info(
# #                 "Payment added: entry=%s cash=%s balance=%s advance=%s",
# #                 updated.id, updated.cash_received, updated.balance, updated.advance_amount,
# #             )

# #             logger.info(
# #                 "Khata update FINAL SUCCESS: entry_id=%s user_id=%s total_bill=%s "
# #                 "cash_received=%s balance=%s is_cleared=%s",
# #                 entry_id,
# #                 user_id,
# #                 getattr(updated, "total_bill", None),
# #                 getattr(updated, "cash_received", None),
# #                 getattr(updated, "balance", None),
# #                 getattr(updated, "is_cleared", None),
# #             )

# #             return self._attach_computed_fields(updated)

# #         except NotFoundException:
# #             logger.warning(
# #                 "Khata update NOT FOUND: entry_id=%s user_id=%s",
# #                 entry_id,
# #                 user_id,
# #             )
# #             raise AppException(status_code=404, detail="Khata entry not found")

# #         except AppException:
# #             raise

# #         except SQLAlchemyError as exc:
# #             _log_db_exception(
# #                 "Khata payment database error",
# #                 exc,
# #                 entry_id=entry_id,
# #                 user_id=user_id,
# #             )
# #             raise AppException(
# #                 status_code=500,
# #                 detail=f"Database error while recording payment: {_db_error(exc)}",
# #             )

# #         except Exception as exc:
# #             logger.error(
# #                 "Khata payment unexpected error: entry_id=%s user_id=%s error_type=%s error=%s",
# #                 entry_id, user_id, type(exc).__name__, str(exc), exc_info=True,
# #             )
# #             raise AppException(
# #                 status_code=500,
# #                 detail=f"Unexpected error while recording payment: {type(exc).__name__}: {str(exc)}",
# #             )
   
# #     def delete_entry(self, entry_id: str, user_id: str) -> bool:
# #         """
# #         Delete a Khata entry.

# #         Rule:
# #         Only fully paid entries can be deleted.
# #         """
# #         try:
# #             logger.info(
# #                 "Khata delete repository lookup START: entry_id=%s user_id=%s",
# #                 entry_id,
# #                 user_id,
# #             )

# #             entry = self.repo.get_entry(entry_id=entry_id, user_id=user_id)

# #             logger.info(
# #                 "Khata delete repository lookup SUCCESS: entry_id=%s is_cleared=%s balance=%s",
# #                 entry_id,
# #                 getattr(entry, "is_cleared", None),
# #                 getattr(entry, "balance", None),
# #             )

# #             if not entry.is_cleared:
# #                 raise AppException(
# #                     status_code=400,
# #                     detail="Cannot delete entry with outstanding balance. Record full payment first.",
# #                 )

# #             logger.info(
# #                 "Khata delete repository write START: entry_id=%s",
# #                 entry_id,
# #             )
# #             result = self.repo.delete_entry(entry)

# #             logger.info(
# #                 "Khata delete repository write SUCCESS: entry_id=%s result=%s",
# #                 entry_id,
# #                 result,
# #             )

# #             logger.info(
# #                 "Khata entry deleted: entry_id=%s user_id=%s",
# #                 entry_id,
# #                 user_id,
# #             )

# #             return result

# #         except NotFoundException:
# #             raise AppException(
# #                 status_code=404,
# #                 detail="Khata entry not found",
# #             )

# #         except AppException:
# #             raise

# #         except SQLAlchemyError as exc:
# #             _log_db_exception(
# #                 "Khata delete database error",
# #                 exc,
# #                 entry_id=entry_id,
# #                 user_id=user_id,
# #             )
# #             raise AppException(
# #                 status_code=500,
# #                 detail=f"Database error while deleting Khata entry: {_db_error(exc)}",
# #             )

# #         except Exception as exc:
# #             logger.error(
# #                 "Khata delete unexpected error: entry_id=%s user_id=%s error_type=%s error=%s",
# #                 entry_id,
# #                 user_id,
# #                 type(exc).__name__,
# #                 str(exc),
# #                 exc_info=True,
# #             )
# #             raise AppException(
# #                 status_code=500,
# #                 detail=f"Unexpected error while deleting Khata entry: {type(exc).__name__}: {str(exc)}",
# #             )


# from uuid import UUID, uuid4
# from datetime import datetime

# from sqlalchemy.exc import SQLAlchemyError, IntegrityError

# from app.models.device import Device
# from app.models.motor_log import MotorLog
# from app.repositories.khata_repo import KhataRepository
# from app.models.khata_entry import KhataEntry
# from app.core.logger import logger
# from app.core.exceptions import AppException, NotFoundException


# def _db_error(exc: Exception) -> str:
#     """
#     Return the real database error message.

#     SQLAlchemy wraps PostgreSQL errors.
#     exc.orig usually contains the actual PostgreSQL error.
#     """
#     return str(exc.orig) if hasattr(exc, "orig") else str(exc)


# def _log_db_exception(operation: str, exc: Exception, **context) -> None:
#     """
#     Log maximum useful SQLAlchemy/PostgreSQL diagnostic information.

#     This is intentionally defensive because not every exception exposes
#     statement/params/orig attributes.
#     """
#     details = {
#         "operation": operation,
#         "error_type": type(exc).__name__,
#         "error": str(exc),
#         "db_error": _db_error(exc),
#     }

#     statement = getattr(exc, "statement", None)
#     params = getattr(exc, "params", None)

#     if statement:
#         details["sql_statement"] = statement

#     if params:
#         details["sql_params"] = params

#     details.update(context)

#     logger.error(
#         "DATABASE FAILURE: %s",
#         " | ".join(f"{key}={value}" for key, value in details.items()),
#         exc_info=True,
#     )


# def _to_float(value) -> float:
#     """
#     Convert Decimal, int, float, string number, or None to float.

#     PostgreSQL Numeric columns often return Decimal.
#     This avoids Decimal and float arithmetic errors.
#     """
#     if value is None:
#         return 0.0

#     try:
#         return float(value)
#     except (TypeError, ValueError) as exc:
#         logger.error(
#             "Numeric conversion failed: value=%s error_type=%s error=%s",
#             value,
#             type(exc).__name__,
#             str(exc),
#             exc_info=True,
#         )
#         raise AppException(
#             status_code=400,
#             detail=f"Invalid numeric value '{value}'",
#         )


# # Detailed flow logs use INFO so they are visible with a normal production
# # logger configuration. SQLAlchemy debug details use ERROR with exc_info=True
# # when a database operation fails.
# class KhataService:
#     """
#     Service layer for Khata ledger entries.

#     MQTT note:
#     - This service does not publish or subscribe MQTT.
#     - ESP32 sends telemetry by MQTT.
#     - Motor start and stop commands use MQTT through MotorService.
#     - Khata uses saved PostgreSQL data such as Device and MotorLog.

#     Responsibilities:
#     - Validate device ownership.
#     - Calculate bill from run hours and price per hour.
#     - Create ledger entries.
#     - Update ledger entries.
#     - Record partial or full payments.
#     - Delete only fully cleared entries.
#     """

#     def __init__(self, db):
#         self.db = db
#         self.repo = KhataRepository(db)

#     @staticmethod
#     def _compute_payment_status(balance: float, cash: float) -> str:
#         """
#         Compute payment status from balance and cash received.

#         Returns:
#             paid, partial, or unpaid
#         """
#         if balance <= 0:
#             return "paid"
#         if cash > 0:
#             return "partial"
#         return "unpaid"

#     @staticmethod
#     def _attach_computed_fields(entry: KhataEntry) -> KhataEntry:

#         balance = _to_float(entry.balance)
#         cash = _to_float(entry.cash_received)

#         logger.debug(
#             "Khata computed fields: entry_id=%s balance=%s cash_received=%s",
#             getattr(entry, "id", None),
#             balance,
#             cash,
#         )

#         entry.remaining_balance = balance

#         entry.payment_status = (
#             KhataService._compute_payment_status(
#                 balance,
#                 cash,
#             )
#         )

#         entry.advance_amount = _to_float(
#             getattr(entry, "advance_amount", 0)
#         )

#         return entry

#     def _get_owned_device(self, user_id: UUID, device_id: str) -> Device:
#         """
#         Get a device owned by the user.

#         Accepts both:
#         - device_uid, for example ESP32_001_TW
#         - internal UUID devices.id

#         Returns:
#             Device ORM object.

#         Raises:
#             AppException if device does not exist or does not belong to user.
#         """
#         logger.info(
#             "Khata device lookup START: user_id=%s requested_device_id=%s",
#             user_id,
#             device_id,
#         )

#         try:
#             logger.info(
#                 "Khata device lookup STEP 1: searching Device.device_uid=%s",
#                 device_id,
#             )
#             device = (
#                 self.db.query(Device)
#                 .filter(Device.device_uid == device_id, Device.user_id == user_id)
#                 .first()
#             )

#             logger.info(
#                 "Khata device lookup STEP 1 RESULT: found=%s device_pk=%s device_uid=%s",
#                 bool(device),
#                 getattr(device, "id", None),
#                 getattr(device, "device_uid", None),
#             )

#             if not device:
#                 logger.info(
#                     "Khata device lookup STEP 2: searching Device.id=%s",
#                     device_id,
#                 )
#                 device = (
#                     self.db.query(Device)
#                     .filter(Device.id == device_id, Device.user_id == user_id)
#                     .first()
#                 )

#                 logger.info(
#                     "Khata device lookup STEP 2 RESULT: found=%s device_pk=%s device_uid=%s",
#                     bool(device),
#                     getattr(device, "id", None),
#                     getattr(device, "device_uid", None),
#                 )

#         except SQLAlchemyError as exc:
#             _log_db_exception(
#                 "Khata device ownership lookup",
#                 exc,
#                 user_id=user_id,
#                 requested_device_id=device_id,
#             )
#             raise AppException(
#                 status_code=500,
#                 detail=f"Database error while looking up device: {_db_error(exc)}",
#             )

#         if not device:
#             logger.warning(
#                 "Khata device lookup denied. Device not found or not owned: user_id=%s device_id=%s",
#                 user_id,
#                 device_id,
#             )
#             raise AppException(
#                 status_code=404,
#                 detail="Device not found or does not belong to you",
#             )

#         return device
#     def create_entry(self, user_id: UUID, data: dict) -> KhataEntry:
        
                
#         """
#         Create a Khata ledger entry.

#         ```
#         Supports:
#         - run_hours directly
#         - motor_log_id based billing
#         - partial payment
#         - full payment
#         - advance payment
#         """

#         try:
#             logger.info(
#                 "Khata create START: user_id=%s customer=%s device_id=%s motor_log_id=%s "
#                 "run_hours=%s price_per_hour=%s cash_received=%s date=%s",
#                 user_id,
#                 data.get("customer_name"),
#                 data.get("device_id"),
#                 data.get("motor_log_id"),
#                 data.get("run_hours"),
#                 data.get("price_per_hour"),
#                 data.get("cash_received"),
#                 data.get("date"),
#             )

#             # ---------------------------------------------------------
#             # Validate Device
#             # ---------------------------------------------------------
#             device_id = data.get("device_id")

#             if not device_id:
#                 raise AppException(
#                     status_code=400,
#                     detail="device_id is required",
#                 )

#             logger.info(
#                 "Khata create STEP device validation: user_id=%s device_id=%s",
#                 user_id,
#                 device_id,
#             )

#             device = self._get_owned_device(
#                 user_id=user_id,
#                 device_id=device_id,
#             )

#             logger.info(
#                 "Khata create STEP device validated: db_device_pk=%s db_device_uid=%s",
#                 getattr(device, "id", None),
#                 getattr(device, "device_uid", None),
#             )

#             # KhataEntry.device_id is a public device UID string.
#             db_device_id = device.device_uid
#             data["device_id"] = db_device_id

#             # ---------------------------------------------------------
#             # Default Date
#             # ---------------------------------------------------------
#             if not data.get("date"):
#                 data["date"] = datetime.now().date()

#             # ---------------------------------------------------------
#             # Motor Log Billing
#             # ---------------------------------------------------------
#             if data.get("motor_log_id"):

#                 logger.info(
#                     "Khata create STEP motor log lookup START: motor_log_id=%s device_id=%s",
#                     data.get("motor_log_id"),
#                     db_device_id,
#                 )

#                 # MotorLog.id is a PostgreSQL UUID.
#                 # Keep the existing motor-log flow, but validate/convert it as UUID
#                 # instead of int. The previous int(...) conversion caused valid
#                 # MotorLog UUIDs to fail before Khata creation.
#                 try:
#                     raw_motor_log_id = data["motor_log_id"]
#                     motor_log_id = (
#                         raw_motor_log_id
#                         if isinstance(raw_motor_log_id, UUID)
#                         else UUID(str(raw_motor_log_id))
#                     )
#                     data["motor_log_id"] = motor_log_id
#                 except (TypeError, ValueError, AttributeError) as exc:
#                     logger.error(
#                         "Khata motor_log_id UUID conversion failed: value=%s type=%s error=%s",
#                         data.get("motor_log_id"),
#                         type(data.get("motor_log_id")).__name__,
#                         str(exc),
#                         exc_info=True,
#                     )
#                     raise AppException(
#                         status_code=400,
#                         detail="motor_log_id must be a valid UUID",
#                     )

#                 try:
#                     log = (
#                         self.db.query(MotorLog)
#                         .filter(
#                             MotorLog.id == motor_log_id,
#                             MotorLog.device_id == db_device_id,
#                         )
#                         .first()
#                     )

#                     logger.info(
#                         "Khata create STEP motor log lookup RESULT: found=%s "
#                         "id=%s device_id=%s start_time=%s end_time=%s",
#                         bool(log),
#                         getattr(log, "id", None),
#                         getattr(log, "device_id", None),
#                         getattr(log, "start_time", None),
#                         getattr(log, "end_time", None),
#                     )
#                 except SQLAlchemyError as exc:
#                     _log_db_exception(
#                         "Khata motor log lookup",
#                         exc,
#                         user_id=user_id,
#                         motor_log_id=motor_log_id,
#                         device_id=db_device_id,
#                     )
#                     raise AppException(
#                         status_code=500,
#                         detail=f"Database error while reading motor log: {_db_error(exc)}",
#                     )

#                 if not log:
#                     raise AppException(
#                         status_code=404,
#                         detail="Motor log not found for this device",
#                     )

#                 if not log.start_time:
#                     raise AppException(
#                         status_code=400,
#                         detail="Motor log has no start_time and cannot open a Khata session.",
#                     )

#                 # -----------------------------------------------------
#                 # OPEN / CLOSED MOTOR SESSION SUPPORT
#                 # -----------------------------------------------------
#                 # A Khata entry must be allowed to exist while the motor is
#                 # still running. Previously this code required end_time, so
#                 # startMotorKhataSession() could never create an open Khata
#                 # entry from an active MotorLog.
#                 #
#                 # started_at / ended_at / is_open already exist on KhataEntry,
#                 # so we populate them here without removing any existing flow.
#                 data["started_at"] = log.start_time

#                 if log.end_time:
#                     run_seconds = max(
#                         0.0,
#                         (log.end_time - log.start_time).total_seconds(),
#                     )

#                     data["run_hours"] = round(
#                         run_seconds / 3600,
#                         2,
#                     )
#                     data["ended_at"] = log.end_time
#                     data["is_open"] = False

#                     logger.info(
#                         "Khata motor billing calculation: motor_log_id=%s start=%s end=%s "
#                         "run_seconds=%s run_hours=%s session=open:%s",
#                         motor_log_id,
#                         log.start_time,
#                         log.end_time,
#                         run_seconds,
#                         data["run_hours"],
#                         data["is_open"],
#                     )
#                 else:
#                     # Motor is still running. Create the Khata session now.
#                     # Billing remains zero until the session is finalized.
#                     data["run_hours"] = 0.0
#                     data["ended_at"] = None
#                     data["is_open"] = True

#                     logger.info(
#                         "Khata OPEN motor session: motor_log_id=%s start=%s "
#                         "run_hours=%s is_open=%s",
#                         motor_log_id,
#                         log.start_time,
#                         data["run_hours"],
#                         data["is_open"],
#                     )

#                 logger.info(
#                     "Khata run_hours resolved from motor log: motor_log_id=%s run_hours=%s is_open=%s",
#                     data["motor_log_id"],
#                     data["run_hours"],
#                     data.get("is_open"),
#                 )

#             # ---------------------------------------------------------
#             # Validation
#             # ---------------------------------------------------------
#             # Open motor sessions are valid with run_hours == 0.0.
#             # Closed/manual entries still require a positive run duration.
#             is_open_session = bool(data.get("is_open", False))

#             if data.get("run_hours") is None:
#                 raise AppException(
#                     status_code=400,
#                     detail="run_hours is required. Supply it directly or provide motor_log_id.",
#                 )

#             if data.get("price_per_hour") is None:
#                 raise AppException(
#                     status_code=400,
#                     detail="price_per_hour is required",
#                 )

#             run_hours = round(
#                 _to_float(data["run_hours"]),
#                 2,
#             )

#             price_per_hour = round(
#                 _to_float(data["price_per_hour"]),
#                 2,
#             )

#             cash_received = round(
#                 _to_float(data.get("cash_received")),
#                 2,
#             )

#             if run_hours < 0:
#                 raise AppException(
#                     status_code=400,
#                     detail="run_hours cannot be negative",
#                 )

#             if not is_open_session and run_hours <= 0:
#                 raise AppException(
#                     status_code=400,
#                     detail="run_hours must be greater than 0 for a closed Khata entry",
#                 )

#             if price_per_hour < 0:
#                 raise AppException(
#                     status_code=400,
#                     detail="price_per_hour cannot be negative",
#                 )

#             if cash_received < 0:
#                 raise AppException(
#                     status_code=400,
#                     detail="cash_received cannot be negative",
#                 )

#             # ---------------------------------------------------------
#             # Bill Calculation
#             # ---------------------------------------------------------
#             total_bill = round(
#                 run_hours * price_per_hour,
#                 2,
#             )

#             if is_open_session:
#                 logger.info(
#                     "Khata OPEN session created with provisional billing: "
#                     "run_hours=%s total_bill=%s. Final duration/bill will be calculated on close.",
#                     run_hours,
#                     total_bill,
#                 )

#             logger.info(
#                 "Khata billing calculation: run_hours=%s price_per_hour=%s "
#                 "total_bill=%s cash_received=%s",
#                 run_hours,
#                 price_per_hour,
#                 total_bill,
#                 cash_received,
#             )

#             if cash_received >= total_bill:

#                 advance_amount = round(
#                     cash_received - total_bill,
#                     2,
#                 )

#                 balance = 0
#                 is_cleared = True

#             else:

#                 advance_amount = 0

#                 balance = round(
#                     total_bill - cash_received,
#                     2,
#                 )

#                 is_cleared = False

#             # ---------------------------------------------------------
#             # Save Values
#             # ---------------------------------------------------------
#             data.update(
#                 run_hours=run_hours,
#                 price_per_hour=price_per_hour,
#                 total_bill=total_bill,
#                 cash_received=cash_received,
#                 balance=balance,
#                 advance_amount=advance_amount,
#                 is_cleared=is_cleared,
#             )

#             # Remove client-controlled fields
#             for field in (
#                 "remaining_balance",
#                 "payment_status",
#                 "user_id",
#             ):
#                 data.pop(field, None)

#             # ---------------------------------------------------------
#             # Create Entry
#             # ---------------------------------------------------------
#             logger.info(
#                 "Khata ORM object creation: user_id=%s device_id=%s data_keys=%s "
#                 "total_bill=%s balance=%s cash_received=%s is_cleared=%s",
#                 user_id,
#                 db_device_id,
#                 list(data.keys()),
#                 data.get("total_bill"),
#                 data.get("balance"),
#                 data.get("cash_received"),
#                 data.get("is_cleared"),
#             )

#             entry = KhataEntry(
#                 user_id=user_id,
#                 **data,
#             )

#             logger.info("Khata repository create START: user_id=%s", user_id)
#             created = self.repo.create_entry(entry)
#             logger.info(
#                 "Khata repository create SUCCESS: id=%s",
#                 getattr(created, "id", None),
#             )

#             logger.info(
#                 "Khata entry created: id=%s user_id=%s device_id=%s total_bill=%s cash=%s balance=%s advance=%s",
#                 created.id,
#                 user_id,
#                 db_device_id,
#                 created.total_bill,
#                 created.cash_received,
#                 created.balance,
#                 created.advance_amount,
#             )

#             return self._attach_computed_fields(created)

#         except AppException:
#             raise

#         except IntegrityError as exc:
#             _log_db_exception(
#                 "Khata create integrity error",
#                 exc,
#                 user_id=user_id,
#                 device_id=data.get("device_id"),
#                 motor_log_id=data.get("motor_log_id"),
#                 data_keys=list(data.keys()),
#             )

#             raise AppException(
#                 status_code=400,
#                 detail=f"Khata create failed. DB error: {_db_error(exc)}",
#             )

#         except SQLAlchemyError as exc:
#             _log_db_exception(
#                 "Khata create database error",
#                 exc,
#                 user_id=user_id,
#                 device_id=data.get("device_id"),
#                 motor_log_id=data.get("motor_log_id"),
#                 data_keys=list(data.keys()),
#             )

#             raise AppException(
#                 status_code=500,
#                 detail=f"Database error while creating Khata entry: {_db_error(exc)}",
#             )

#         except Exception as exc:
#             logger.error(
#                 "Khata create unexpected error: user_id=%s error_type=%s error=%s",
#                 user_id,
#                 type(exc).__name__,
#                 str(exc),
#                 exc_info=True,
#             )

#             raise AppException(
#                 status_code=500,
#                 detail=f"Unexpected error while creating Khata entry: {type(exc).__name__}: {str(exc)}",
#             )
        

#     def get_all_entries(self, user_id: UUID) -> list[KhataEntry]:
#         """
#         Return all Khata entries owned by one user.
#         """
#         try:
#             logger.info(
#                 "Khata get_all START: user_id=%s repo=%s db=%s",
#                 user_id,
#                 type(self.repo).__name__,
#                 type(self.db).__name__,
#             )

#             logger.info(
#                 "Khata get_all repository query START: user_id=%s",
#                 user_id,
#             )

#             entries = self.repo.get_all_entries(user_id)

#             logger.info(
#                 "Khata get_all repository query SUCCESS: user_id=%s count=%s",
#                 user_id,
#                 len(entries),
#             )

#             for index, entry in enumerate(entries):
#                 logger.debug(
#                     "Khata get_all entry[%s]: id=%s device_id=%s customer=%s "
#                     "run_hours=%s price_per_hour=%s total_bill=%s cash_received=%s "
#                     "balance=%s is_cleared=%s",
#                     index,
#                     getattr(entry, "id", None),
#                     getattr(entry, "device_id", None),
#                     getattr(entry, "customer_name", None),
#                     getattr(entry, "run_hours", None),
#                     getattr(entry, "price_per_hour", None),
#                     getattr(entry, "total_bill", None),
#                     getattr(entry, "cash_received", None),
#                     getattr(entry, "balance", None),
#                     getattr(entry, "is_cleared", None),
#                 )
#                 self._attach_computed_fields(entry)

#             logger.info(
#                 "Khata get_all SUCCESS: user_id=%s count=%s",
#                 user_id,
#                 len(entries),
#             )

#             return entries

#         except AppException:
#             raise

#         except SQLAlchemyError as exc:
#             _log_db_exception(
#                 "Khata get_all database error",
#                 exc,
#                 user_id=user_id,
#             )
#             raise AppException(
#                 status_code=500,
#                 detail=f"Database error while fetching Khata entries: {_db_error(exc)}",
#             )

#         except Exception as exc:
#             logger.error(
#                 "Khata fetch all unexpected error: user_id=%s error_type=%s error=%s",
#                 user_id,
#                 type(exc).__name__,
#                 str(exc),
#                 exc_info=True,
#             )
#             raise AppException(
#                 status_code=500,
#                 detail=f"Unexpected error while fetching Khata entries: {type(exc).__name__}: {str(exc)}",
#             )

#     def get_entry(self, entry_id: str, user_id: UUID) -> KhataEntry:
#         """
#         Return one Khata entry and enforce user ownership.
#         """
#         try:
#             entry = self.repo.get_entry(entry_id=entry_id, user_id=user_id)

#             logger.info(
#                 "Khata entry fetched: entry_id=%s user_id=%s",
#                 entry_id,
#                 user_id,
#             )

#             return self._attach_computed_fields(entry)

#         except NotFoundException:
#             logger.warning(
#                 "Khata entry not found: entry_id=%s user_id=%s",
#                 entry_id,
#                 user_id,
#             )
#             raise AppException(
#                 status_code=404,
#                 detail="Khata entry not found",
#             )

#         except AppException:
#             raise

#         except SQLAlchemyError as exc:
#             _log_db_exception(
#                 "Khata get database error",
#                 exc,
#                 entry_id=entry_id,
#                 user_id=user_id,
#             )
#             raise AppException(
#                 status_code=500,
#                 detail=f"Database error while fetching Khata entry: {_db_error(exc)}",
#             )

#         except Exception as exc:
#             logger.error(
#                 "Khata get unexpected error: entry_id=%s user_id=%s error_type=%s error=%s",
#                 entry_id,
#                 user_id,
#                 type(exc).__name__,
#                 str(exc),
#                 exc_info=True,
#             )
#             raise AppException(
#                 status_code=500,
#                 detail=f"Unexpected error while fetching Khata entry: {type(exc).__name__}: {str(exc)}",
#             )

#     def update_entry(
#         self,
#         entry_id: str,
#         user_id: UUID,
#         data: dict,
#     ) -> KhataEntry:
#         try:
#             logger.info(
#                 "Khata update requested: entry_id=%s user_id=%s",
#                 entry_id,
#                 user_id,
#             )

#             logger.info(
#                 "Khata update repository lookup START: entry_id=%s user_id=%s",
#                 entry_id,
#                 user_id,
#             )

#             entry = self.repo.get_entry(
#                 entry_id=entry_id,
#                 user_id=user_id,
#             )

#             logger.info(
#                 "Khata update repository lookup SUCCESS: entry_id=%s current_device=%s "
#                 "current_total_bill=%s current_cash=%s current_balance=%s",
#                 entry_id,
#                 getattr(entry, "device_id", None),
#                 getattr(entry, "total_bill", None),
#                 getattr(entry, "cash_received", None),
#                 getattr(entry, "balance", None),
#             )

#             clean_data = {k: v for k, v in data.items() if v is not None}

#             # ---------------------------------------------------------
#             # AUTO-FINALIZE LINKED MOTOR SESSION
#             # ---------------------------------------------------------
#             # If this Khata entry was created while the motor was running,
#             # it starts with run_hours=0 and is_open=True. When an update
#             # happens after MotorLog.end_time has been saved, use the
#             # authoritative MotorLog timestamps to finalize the session.
#             linked_motor_log_id = getattr(entry, "motor_log_id", None)

#             if linked_motor_log_id:
#                 try:
#                     linked_log = (
#                         self.db.query(MotorLog)
#                         .filter(
#                             MotorLog.id == linked_motor_log_id,
#                             MotorLog.device_id == entry.device_id,
#                         )
#                         .first()
#                     )
#                 except SQLAlchemyError as exc:
#                     _log_db_exception(
#                         "Khata update linked motor log lookup",
#                         exc,
#                         entry_id=entry_id,
#                         user_id=user_id,
#                         motor_log_id=linked_motor_log_id,
#                         device_id=getattr(entry, "device_id", None),
#                     )
#                     raise AppException(
#                         status_code=500,
#                         detail=f"Database error while finalizing motor session: {_db_error(exc)}",
#                     )

#                 if (
#                     linked_log
#                     and linked_log.start_time
#                     and linked_log.end_time
#                 ):
#                     run_seconds = max(
#                         0.0,
#                         (
#                             linked_log.end_time
#                             - linked_log.start_time
#                         ).total_seconds(),
#                     )

#                     clean_data["run_hours"] = round(
#                         run_seconds / 3600,
#                         2,
#                     )
#                     clean_data["started_at"] = linked_log.start_time
#                     clean_data["ended_at"] = linked_log.end_time
#                     clean_data["is_open"] = False

#                     logger.info(
#                         "Khata linked motor session FINALIZED: entry_id=%s "
#                         "motor_log_id=%s start=%s end=%s run_seconds=%s "
#                         "run_hours=%s is_open=%s",
#                         entry_id,
#                         linked_motor_log_id,
#                         linked_log.start_time,
#                         linked_log.end_time,
#                         run_seconds,
#                         clean_data["run_hours"],
#                         clean_data["is_open"],
#                     )

#             logger.info(
#                 "Khata update clean payload: entry_id=%s fields=%s",
#                 entry_id,
#                 list(clean_data.keys()),
#             )

#             if "run_hours" in clean_data:
#                 clean_data["run_hours"] = round(_to_float(clean_data["run_hours"]), 2)
#             if "price_per_hour" in clean_data:
#                 clean_data["price_per_hour"] = round(_to_float(clean_data["price_per_hour"]), 2)
#             if "cash_received" in clean_data:
#                 clean_data["cash_received"] = round(_to_float(clean_data["cash_received"]), 2)

#             logger.info(
#                 "Khata update repository write #1 START: entry_id=%s",
#                 entry_id,
#             )
#             updated = self.repo.update_entry(entry, clean_data)

#             logger.info(
#                 "Khata update repository write #1 SUCCESS: entry_id=%s",
#                 entry_id,
#             )

#             run_hours = _to_float(updated.run_hours)
#             price_per_hour = _to_float(updated.price_per_hour)
#             cash_received = _to_float(updated.cash_received)

#             total_bill = round(run_hours * price_per_hour, 2)

#             if cash_received >= total_bill:
#                 advance_amount = round(cash_received - total_bill, 2)
#                 balance = 0
#                 is_cleared = True
#             else:
#                 advance_amount = 0
#                 balance = round(total_bill - cash_received, 2)
#                 is_cleared = False

#             logger.info(
#                 "Khata update recalculation: entry_id=%s run_hours=%s price_per_hour=%s "
#                 "cash_received=%s total_bill=%s balance=%s advance=%s is_cleared=%s",
#                 entry_id,
#                 run_hours,
#                 price_per_hour,
#                 cash_received,
#                 total_bill,
#                 balance,
#                 advance_amount,
#                 is_cleared,
#             )

#             updated = self.repo.update_entry(
#                 updated,
#                 {
#                     "total_bill": total_bill,
#                     "balance": balance,
#                     "advance_amount": advance_amount,
#                     "is_cleared": is_cleared,
#                 },
#             )

#             logger.info(
#                 "Khata update SUCCESS: entry_id=%s",
#                 entry_id,
#             )

#             return self._attach_computed_fields(updated)

#         except NotFoundException:
#             raise AppException(status_code=404, detail="Khata entry not found")
        
#         except AppException:
#             raise

#         except SQLAlchemyError as exc:
#             _log_db_exception(
#                 "Khata update database error",
#                 exc,
#                 entry_id=entry_id,
#                 user_id=user_id,
#             )
#             raise AppException(
#                 status_code=500,
#                 detail=f"Database error while updating Khata entry: {_db_error(exc)}",
#             )

#         except Exception as exc:
#             logger.error(
#                 "Khata update unexpected error: entry_id=%s user_id=%s error_type=%s error=%s",
#                 entry_id, user_id, type(exc).__name__, str(exc), exc_info=True,
#             )
#             raise AppException(
#                 status_code=500,
#                 detail=f"Unexpected error while updating Khata entry: {type(exc).__name__}: {str(exc)}",
#             )

#     def update_payment(
#         self,
#         entry_id: str,
#         user_id: UUID,
#         cash_received: float,
#     ) -> KhataEntry:
#         try:
#             if cash_received <= 0:
#                 raise AppException(status_code=400, detail="cash_received must be greater than 0")

#             logger.info(
#                 "Khata payment repository lookup START: entry_id=%s user_id=%s cash_received=%s",
#                 entry_id,
#                 user_id,
#                 cash_received,
#             )

#             entry = self.repo.get_entry(entry_id=entry_id, user_id=user_id)

#             logger.info(
#                 "Khata payment repository lookup SUCCESS: entry_id=%s current_cash=%s "
#                 "total_bill=%s balance=%s",
#                 entry_id,
#                 getattr(entry, "cash_received", None),
#                 getattr(entry, "total_bill", None),
#                 getattr(entry, "balance", None),
#             )

#             current_cash = _to_float(entry.cash_received)
#             total_cash = round(current_cash + cash_received, 2)
#             total_bill = _to_float(entry.total_bill)

#             if total_cash >= total_bill:
#                 advance_amount = round(total_cash - total_bill, 2)
#                 balance = 0
#                 is_cleared = True
#             else:
#                 advance_amount = 0
#                 balance = round(total_bill - total_cash, 2)
#                 is_cleared = False

#             logger.info(
#                 "Khata payment calculation: entry_id=%s current_cash=%s new_payment=%s "
#                 "total_cash=%s total_bill=%s balance=%s advance=%s is_cleared=%s",
#                 entry_id,
#                 current_cash,
#                 cash_received,
#                 total_cash,
#                 total_bill,
#                 balance,
#                 advance_amount,
#                 is_cleared,
#             )

#             updated = self.repo.update_entry(
#                 entry,
#                 {
#                     "cash_received": total_cash,
#                     "balance": balance,
#                     "advance_amount": advance_amount,
#                     "is_cleared": is_cleared,
#                 },
#             )

#             logger.info(
#                 "Payment added: entry=%s cash=%s balance=%s advance=%s",
#                 updated.id, updated.cash_received, updated.balance, updated.advance_amount,
#             )

#             logger.info(
#                 "Khata update FINAL SUCCESS: entry_id=%s user_id=%s total_bill=%s "
#                 "cash_received=%s balance=%s is_cleared=%s",
#                 entry_id,
#                 user_id,
#                 getattr(updated, "total_bill", None),
#                 getattr(updated, "cash_received", None),
#                 getattr(updated, "balance", None),
#                 getattr(updated, "is_cleared", None),
#             )

#             return self._attach_computed_fields(updated)

#         except NotFoundException:
#             logger.warning(
#                 "Khata update NOT FOUND: entry_id=%s user_id=%s",
#                 entry_id,
#                 user_id,
#             )
#             raise AppException(status_code=404, detail="Khata entry not found")

#         except AppException:
#             raise

#         except SQLAlchemyError as exc:
#             _log_db_exception(
#                 "Khata payment database error",
#                 exc,
#                 entry_id=entry_id,
#                 user_id=user_id,
#             )
#             raise AppException(
#                 status_code=500,
#                 detail=f"Database error while recording payment: {_db_error(exc)}",
#             )

#         except Exception as exc:
#             logger.error(
#                 "Khata payment unexpected error: entry_id=%s user_id=%s error_type=%s error=%s",
#                 entry_id, user_id, type(exc).__name__, str(exc), exc_info=True,
#             )
#             raise AppException(
#                 status_code=500,
#                 detail=f"Unexpected error while recording payment: {type(exc).__name__}: {str(exc)}",
#             )
   
#     def delete_entry(self, entry_id: str, user_id: str) -> bool:
#         """
#         Delete a Khata entry.

#         Rule:
#         Only fully paid entries can be deleted.
#         """
#         try:
#             logger.info(
#                 "Khata delete repository lookup START: entry_id=%s user_id=%s",
#                 entry_id,
#                 user_id,
#             )

#             entry = self.repo.get_entry(entry_id=entry_id, user_id=user_id)

#             logger.info(
#                 "Khata delete repository lookup SUCCESS: entry_id=%s is_cleared=%s balance=%s",
#                 entry_id,
#                 getattr(entry, "is_cleared", None),
#                 getattr(entry, "balance", None),
#             )

#             if not entry.is_cleared:
#                 raise AppException(
#                     status_code=400,
#                     detail="Cannot delete entry with outstanding balance. Record full payment first.",
#                 )

#             logger.info(
#                 "Khata delete repository write START: entry_id=%s",
#                 entry_id,
#             )
#             result = self.repo.delete_entry(entry)

#             logger.info(
#                 "Khata delete repository write SUCCESS: entry_id=%s result=%s",
#                 entry_id,
#                 result,
#             )

#             logger.info(
#                 "Khata entry deleted: entry_id=%s user_id=%s",
#                 entry_id,
#                 user_id,
#             )

#             return result

#         except NotFoundException:
#             raise AppException(
#                 status_code=404,
#                 detail="Khata entry not found",
#             )

#         except AppException:
#             raise

#         except SQLAlchemyError as exc:
#             _log_db_exception(
#                 "Khata delete database error",
#                 exc,
#                 entry_id=entry_id,
#                 user_id=user_id,
#             )
#             raise AppException(
#                 status_code=500,
#                 detail=f"Database error while deleting Khata entry: {_db_error(exc)}",
#             )

#         except Exception as exc:
#             logger.error(
#                 "Khata delete unexpected error: entry_id=%s user_id=%s error_type=%s error=%s",
#                 entry_id,
#                 user_id,
#                 type(exc).__name__,
#                 str(exc),
#                 exc_info=True,
#             )
#             raise AppException(
#                 status_code=500,
#                 detail=f"Unexpected error while deleting Khata entry: {type(exc).__name__}: {str(exc)}",
#             )


from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.models.device import Device
from app.models.motor_log import MotorLog
from app.repositories.khata_repo import KhataRepository
from app.models.khata_entry import KhataEntry
from app.core.logger import logger
from app.core.exceptions import AppException, NotFoundException


def _db_error(exc: Exception) -> str:
    """
    Return the real database error message.

    SQLAlchemy wraps PostgreSQL errors.
    exc.orig usually contains the actual PostgreSQL error.
    """
    return str(exc.orig) if hasattr(exc, "orig") else str(exc)


def _log_db_exception(operation: str, exc: Exception, **context) -> None:
    """
    Log maximum useful SQLAlchemy/PostgreSQL diagnostic information.

    This is intentionally defensive because not every exception exposes
    statement/params/orig attributes.
    """
    details = {
        "operation": operation,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "db_error": _db_error(exc),
    }

    statement = getattr(exc, "statement", None)
    params = getattr(exc, "params", None)

    if statement:
        details["sql_statement"] = statement

    if params:
        details["sql_params"] = params

    details.update(context)

    logger.error(
        "DATABASE FAILURE: %s",
        " | ".join(f"{key}={value}" for key, value in details.items()),
        exc_info=True,
    )


def _to_float(value) -> float:
    """
    Convert Decimal, int, float, string number, or None to float.

    PostgreSQL Numeric columns often return Decimal.
    This avoids Decimal and float arithmetic errors.
    """
    if value is None:
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        logger.error(
            "Numeric conversion failed: value=%s error_type=%s error=%s",
            value,
            type(exc).__name__,
            str(exc),
            exc_info=True,
        )
        raise AppException(
            status_code=400,
            detail=f"Invalid numeric value '{value}'",
        )


# Detailed flow logs use INFO so they are visible with a normal production
# logger configuration. SQLAlchemy debug details use ERROR with exc_info=True
# when a database operation fails.
class KhataService:
    """
    Service layer for Khata ledger entries.

    MQTT note:
    - This service does not publish or subscribe MQTT.
    - ESP32 sends telemetry by MQTT.
    - Motor start and stop commands use MQTT through MotorService.
    - Khata uses saved PostgreSQL data such as Device and MotorLog.

    Responsibilities:
    - Validate device ownership.
    - Calculate bill from run hours and price per hour.
    - Create ledger entries.
    - Update ledger entries.
    - Record partial or full payments.
    - Delete closed entries; protect active/open motor sessions.
    """

    def __init__(self, db):
        self.db = db
        self.repo = KhataRepository(db)

    @staticmethod
    def _compute_payment_status(balance: float, cash: float) -> str:
        """
        Compute payment status from balance and cash received.

        Returns:
            paid, partial, or unpaid
        """
        if balance <= 0:
            return "paid"
        if cash > 0:
            return "partial"
        return "unpaid"

    @staticmethod
    def _attach_computed_fields(entry: KhataEntry) -> KhataEntry:

        balance = _to_float(entry.balance)
        cash = _to_float(entry.cash_received)

        logger.debug(
            "Khata computed fields: entry_id=%s balance=%s cash_received=%s",
            getattr(entry, "id", None),
            balance,
            cash,
        )

        entry.remaining_balance = balance

        is_open = bool(getattr(entry, "is_open", False))
        total_bill = _to_float(getattr(entry, "total_bill", 0))
        price_per_hour = _to_float(getattr(entry, "price_per_hour", 0))

        # An active motor session is provisional and must never display PAID.
        # A closed session with no rate/bill is also pending rate, not paid.
        if is_open or (total_bill <= 0 and price_per_hour <= 0):
            entry.payment_status = "unpaid"
        else:
            entry.payment_status = (
                KhataService._compute_payment_status(
                    balance,
                    cash,
                )
            )

        entry.advance_amount = _to_float(
            getattr(entry, "advance_amount", 0)
        )

        return entry

    def _get_owned_device(self, user_id: UUID, device_id: str) -> Device:
        """
        Get a device owned by the user.

        Accepts both:
        - device_uid, for example ESP32_001_TW
        - internal UUID devices.id

        Returns:
            Device ORM object.

        Raises:
            AppException if device does not exist or does not belong to user.
        """
        logger.info(
            "Khata device lookup START: user_id=%s requested_device_id=%s",
            user_id,
            device_id,
        )

        try:
            logger.info(
                "Khata device lookup STEP 1: searching Device.device_uid=%s",
                device_id,
            )
            device = (
                self.db.query(Device)
                .filter(Device.device_uid == device_id, Device.user_id == user_id)
                .first()
            )

            logger.info(
                "Khata device lookup STEP 1 RESULT: found=%s device_pk=%s device_uid=%s",
                bool(device),
                getattr(device, "id", None),
                getattr(device, "device_uid", None),
            )

            if not device:
                logger.info(
                    "Khata device lookup STEP 2: searching Device.id=%s",
                    device_id,
                )
                device = (
                    self.db.query(Device)
                    .filter(Device.id == device_id, Device.user_id == user_id)
                    .first()
                )

                logger.info(
                    "Khata device lookup STEP 2 RESULT: found=%s device_pk=%s device_uid=%s",
                    bool(device),
                    getattr(device, "id", None),
                    getattr(device, "device_uid", None),
                )

        except SQLAlchemyError as exc:
            _log_db_exception(
                "Khata device ownership lookup",
                exc,
                user_id=user_id,
                requested_device_id=device_id,
            )
            raise AppException(
                status_code=500,
                detail=f"Database error while looking up device: {_db_error(exc)}",
            )

        if not device:
            logger.warning(
                "Khata device lookup denied. Device not found or not owned: user_id=%s device_id=%s",
                user_id,
                device_id,
            )
            raise AppException(
                status_code=404,
                detail="Device not found or does not belong to you",
            )

        return device
    def create_entry(self, user_id: UUID, data: dict) -> KhataEntry:
        
                
        """
        Create a Khata ledger entry.

        ```
        Supports:
        - run_hours directly
        - motor_log_id based billing
        - partial payment
        - full payment
        - advance payment
        """

        try:
            logger.info(
                "Khata create START: user_id=%s customer=%s device_id=%s motor_log_id=%s "
                "run_hours=%s price_per_hour=%s cash_received=%s date=%s",
                user_id,
                data.get("customer_name"),
                data.get("device_id"),
                data.get("motor_log_id"),
                data.get("run_hours"),
                data.get("price_per_hour"),
                data.get("cash_received"),
                data.get("date"),
            )

            # ---------------------------------------------------------
            # Validate Device
            # ---------------------------------------------------------
            device_id = data.get("device_id")

            if not device_id:
                raise AppException(
                    status_code=400,
                    detail="device_id is required",
                )

            logger.info(
                "Khata create STEP device validation: user_id=%s device_id=%s",
                user_id,
                device_id,
            )

            device = self._get_owned_device(
                user_id=user_id,
                device_id=device_id,
            )

            logger.info(
                "Khata create STEP device validated: db_device_pk=%s db_device_uid=%s",
                getattr(device, "id", None),
                getattr(device, "device_uid", None),
            )

            # KhataEntry.device_id is a public device UID string.
            db_device_id = device.device_uid
            data["device_id"] = db_device_id

            # ---------------------------------------------------------
            # Default Date
            # ---------------------------------------------------------
            if not data.get("date"):
                data["date"] = datetime.now().date()

            # ---------------------------------------------------------
            # Motor Log Billing
            # ---------------------------------------------------------
            if data.get("motor_log_id"):

                logger.info(
                    "Khata create STEP motor log lookup START: motor_log_id=%s device_id=%s",
                    data.get("motor_log_id"),
                    db_device_id,
                )

                # MotorLog.id is a PostgreSQL UUID.
                # Keep the existing motor-log flow, but validate/convert it as UUID
                # instead of int. The previous int(...) conversion caused valid
                # MotorLog UUIDs to fail before Khata creation.
                try:
                    raw_motor_log_id = data["motor_log_id"]
                    motor_log_id = (
                        raw_motor_log_id
                        if isinstance(raw_motor_log_id, UUID)
                        else UUID(str(raw_motor_log_id))
                    )
                    data["motor_log_id"] = motor_log_id
                except (TypeError, ValueError, AttributeError) as exc:
                    logger.error(
                        "Khata motor_log_id UUID conversion failed: value=%s type=%s error=%s",
                        data.get("motor_log_id"),
                        type(data.get("motor_log_id")).__name__,
                        str(exc),
                        exc_info=True,
                    )
                    raise AppException(
                        status_code=400,
                        detail="motor_log_id must be a valid UUID",
                    )

                try:
                    log = (
                        self.db.query(MotorLog)
                        .filter(
                            MotorLog.id == motor_log_id,
                            MotorLog.device_id == db_device_id,
                        )
                        .first()
                    )

                    logger.info(
                        "Khata create STEP motor log lookup RESULT: found=%s "
                        "id=%s device_id=%s start_time=%s end_time=%s",
                        bool(log),
                        getattr(log, "id", None),
                        getattr(log, "device_id", None),
                        getattr(log, "start_time", None),
                        getattr(log, "end_time", None),
                    )
                except SQLAlchemyError as exc:
                    _log_db_exception(
                        "Khata motor log lookup",
                        exc,
                        user_id=user_id,
                        motor_log_id=motor_log_id,
                        device_id=db_device_id,
                    )
                    raise AppException(
                        status_code=500,
                        detail=f"Database error while reading motor log: {_db_error(exc)}",
                    )

                if not log:
                    raise AppException(
                        status_code=404,
                        detail="Motor log not found for this device",
                    )

                if not log.start_time:
                    raise AppException(
                        status_code=400,
                        detail="Motor log has no start_time and cannot open a Khata session.",
                    )

                # -----------------------------------------------------
                # OPEN / CLOSED MOTOR SESSION SUPPORT
                # -----------------------------------------------------
                # A Khata entry must be allowed to exist while the motor is
                # still running. Previously this code required end_time, so
                # startMotorKhataSession() could never create an open Khata
                # entry from an active MotorLog.
                #
                # started_at / ended_at / is_open already exist on KhataEntry,
                # so we populate them here without removing any existing flow.
                data["started_at"] = log.start_time

                if log.end_time:
                    run_seconds = max(
                        0.0,
                        (log.end_time - log.start_time).total_seconds(),
                    )

                    data["run_hours"] = round(
                        run_seconds / 3600,
                        2,
                    )
                    data["ended_at"] = log.end_time
                    data["is_open"] = False

                    logger.info(
                        "Khata motor billing calculation: motor_log_id=%s start=%s end=%s "
                        "run_seconds=%s run_hours=%s session=open:%s",
                        motor_log_id,
                        log.start_time,
                        log.end_time,
                        run_seconds,
                        data["run_hours"],
                        data["is_open"],
                    )
                else:
                    # Motor is still running. Create the Khata session now.
                    # Billing remains zero until the session is finalized.
                    data["run_hours"] = 0.0
                    data["ended_at"] = None
                    data["is_open"] = True

                    logger.info(
                        "Khata OPEN motor session: motor_log_id=%s start=%s "
                        "run_hours=%s is_open=%s",
                        motor_log_id,
                        log.start_time,
                        data["run_hours"],
                        data["is_open"],
                    )

                logger.info(
                    "Khata run_hours resolved from motor log: motor_log_id=%s run_hours=%s is_open=%s",
                    data["motor_log_id"],
                    data["run_hours"],
                    data.get("is_open"),
                )

            # ---------------------------------------------------------
            # Validation
            # ---------------------------------------------------------
            # Open motor sessions are valid with run_hours == 0.0.
            # Closed/manual entries still require a positive run duration.
            is_open_session = bool(data.get("is_open", False))

            if data.get("run_hours") is None:
                raise AppException(
                    status_code=400,
                    detail="run_hours is required. Supply it directly or provide motor_log_id.",
                )

            if data.get("price_per_hour") is None:
                raise AppException(
                    status_code=400,
                    detail="price_per_hour is required",
                )

            run_hours = round(
                _to_float(data["run_hours"]),
                2,
            )

            price_per_hour = round(
                _to_float(data["price_per_hour"]),
                2,
            )

            cash_received = round(
                _to_float(data.get("cash_received")),
                2,
            )

            if run_hours < 0:
                raise AppException(
                    status_code=400,
                    detail="run_hours cannot be negative",
                )

            if not is_open_session and run_hours <= 0:
                raise AppException(
                    status_code=400,
                    detail="run_hours must be greater than 0 for a closed Khata entry",
                )

            if price_per_hour < 0:
                raise AppException(
                    status_code=400,
                    detail="price_per_hour cannot be negative",
                )

            if cash_received < 0:
                raise AppException(
                    status_code=400,
                    detail="cash_received cannot be negative",
                )

            # ---------------------------------------------------------
            # Bill Calculation
            # ---------------------------------------------------------
            total_bill = round(
                run_hours * price_per_hour,
                2,
            )

            if is_open_session:
                logger.info(
                    "Khata OPEN session created with provisional billing: "
                    "run_hours=%s total_bill=%s. Final duration/bill will be calculated on close.",
                    run_hours,
                    total_bill,
                )

            logger.info(
                "Khata billing calculation: run_hours=%s price_per_hour=%s "
                "total_bill=%s cash_received=%s",
                run_hours,
                price_per_hour,
                total_bill,
                cash_received,
            )

            # IMPORTANT:
            # An OPEN motor session has a provisional run_hours/total_bill of 0.
            # It must NOT be marked cleared/paid simply because 0 >= 0.
            # Final billing/cleared status is calculated after the linked
            # MotorLog receives its real end_time.
            if is_open_session:
                advance_amount = 0
                balance = 0
                is_cleared = False

            elif total_bill <= 0 and price_per_hour <= 0:
                # Closed session/manual entry with no rate yet.
                # Keep it pending so the user can set the rate later.
                advance_amount = 0
                balance = 0
                is_cleared = False

            elif cash_received >= total_bill:

                advance_amount = round(
                    cash_received - total_bill,
                    2,
                )

                balance = 0
                is_cleared = True

            else:

                advance_amount = 0

                balance = round(
                    total_bill - cash_received,
                    2,
                )

                is_cleared = False

            # ---------------------------------------------------------
            # Save Values
            # ---------------------------------------------------------
            data.update(
                run_hours=run_hours,
                price_per_hour=price_per_hour,
                total_bill=total_bill,
                cash_received=cash_received,
                balance=balance,
                advance_amount=advance_amount,
                is_cleared=is_cleared,
            )

            # Remove client-controlled fields
            for field in (
                "remaining_balance",
                "payment_status",
                "user_id",
            ):
                data.pop(field, None)

            # ---------------------------------------------------------
            # Create Entry
            # ---------------------------------------------------------
            logger.info(
                "Khata ORM object creation: user_id=%s device_id=%s data_keys=%s "
                "total_bill=%s balance=%s cash_received=%s is_cleared=%s",
                user_id,
                db_device_id,
                list(data.keys()),
                data.get("total_bill"),
                data.get("balance"),
                data.get("cash_received"),
                data.get("is_cleared"),
            )

            entry = KhataEntry(
                user_id=user_id,
                **data,
            )

            logger.info("Khata repository create START: user_id=%s", user_id)
            created = self.repo.create_entry(entry)
            logger.info(
                "Khata repository create SUCCESS: id=%s",
                getattr(created, "id", None),
            )

            logger.info(
                "Khata entry created: id=%s user_id=%s device_id=%s total_bill=%s cash=%s balance=%s advance=%s",
                created.id,
                user_id,
                db_device_id,
                created.total_bill,
                created.cash_received,
                created.balance,
                created.advance_amount,
            )

            return self._attach_computed_fields(created)

        except AppException:
            raise

        except IntegrityError as exc:
            _log_db_exception(
                "Khata create integrity error",
                exc,
                user_id=user_id,
                device_id=data.get("device_id"),
                motor_log_id=data.get("motor_log_id"),
                data_keys=list(data.keys()),
            )

            raise AppException(
                status_code=400,
                detail=f"Khata create failed. DB error: {_db_error(exc)}",
            )

        except SQLAlchemyError as exc:
            _log_db_exception(
                "Khata create database error",
                exc,
                user_id=user_id,
                device_id=data.get("device_id"),
                motor_log_id=data.get("motor_log_id"),
                data_keys=list(data.keys()),
            )

            raise AppException(
                status_code=500,
                detail=f"Database error while creating Khata entry: {_db_error(exc)}",
            )

        except Exception as exc:
            logger.error(
                "Khata create unexpected error: user_id=%s error_type=%s error=%s",
                user_id,
                type(exc).__name__,
                str(exc),
                exc_info=True,
            )

            raise AppException(
                status_code=500,
                detail=f"Unexpected error while creating Khata entry: {type(exc).__name__}: {str(exc)}",
            )
        

    def get_all_entries(self, user_id: UUID) -> list[KhataEntry]:
        """
        Return all Khata entries owned by one user.
        """
        try:
            logger.info(
                "Khata get_all START: user_id=%s repo=%s db=%s",
                user_id,
                type(self.repo).__name__,
                type(self.db).__name__,
            )

            logger.info(
                "Khata get_all repository query START: user_id=%s",
                user_id,
            )

            entries = self.repo.get_all_entries(user_id)

            logger.info(
                "Khata get_all repository query SUCCESS: user_id=%s count=%s",
                user_id,
                len(entries),
            )

            for index, entry in enumerate(entries):
                logger.debug(
                    "Khata get_all entry[%s]: id=%s device_id=%s customer=%s "
                    "run_hours=%s price_per_hour=%s total_bill=%s cash_received=%s "
                    "balance=%s is_cleared=%s",
                    index,
                    getattr(entry, "id", None),
                    getattr(entry, "device_id", None),
                    getattr(entry, "customer_name", None),
                    getattr(entry, "run_hours", None),
                    getattr(entry, "price_per_hour", None),
                    getattr(entry, "total_bill", None),
                    getattr(entry, "cash_received", None),
                    getattr(entry, "balance", None),
                    getattr(entry, "is_cleared", None),
                )
                self._attach_computed_fields(entry)

            logger.info(
                "Khata get_all SUCCESS: user_id=%s count=%s",
                user_id,
                len(entries),
            )

            return entries

        except AppException:
            raise

        except SQLAlchemyError as exc:
            _log_db_exception(
                "Khata get_all database error",
                exc,
                user_id=user_id,
            )
            raise AppException(
                status_code=500,
                detail=f"Database error while fetching Khata entries: {_db_error(exc)}",
            )

        except Exception as exc:
            logger.error(
                "Khata fetch all unexpected error: user_id=%s error_type=%s error=%s",
                user_id,
                type(exc).__name__,
                str(exc),
                exc_info=True,
            )
            raise AppException(
                status_code=500,
                detail=f"Unexpected error while fetching Khata entries: {type(exc).__name__}: {str(exc)}",
            )

    def get_entry(self, entry_id: str, user_id: UUID) -> KhataEntry:
        """
        Return one Khata entry and enforce user ownership.
        """
        try:
            entry = self.repo.get_entry(entry_id=entry_id, user_id=user_id)

            logger.info(
                "Khata entry fetched: entry_id=%s user_id=%s",
                entry_id,
                user_id,
            )

            return self._attach_computed_fields(entry)

        except NotFoundException:
            logger.warning(
                "Khata entry not found: entry_id=%s user_id=%s",
                entry_id,
                user_id,
            )
            raise AppException(
                status_code=404,
                detail="Khata entry not found",
            )

        except AppException:
            raise

        except SQLAlchemyError as exc:
            _log_db_exception(
                "Khata get database error",
                exc,
                entry_id=entry_id,
                user_id=user_id,
            )
            raise AppException(
                status_code=500,
                detail=f"Database error while fetching Khata entry: {_db_error(exc)}",
            )

        except Exception as exc:
            logger.error(
                "Khata get unexpected error: entry_id=%s user_id=%s error_type=%s error=%s",
                entry_id,
                user_id,
                type(exc).__name__,
                str(exc),
                exc_info=True,
            )
            raise AppException(
                status_code=500,
                detail=f"Unexpected error while fetching Khata entry: {type(exc).__name__}: {str(exc)}",
            )

    def update_entry(
        self,
        entry_id: str,
        user_id: UUID,
        data: dict,
    ) -> KhataEntry:
        try:
            logger.info(
                "Khata update requested: entry_id=%s user_id=%s",
                entry_id,
                user_id,
            )

            logger.info(
                "Khata update repository lookup START: entry_id=%s user_id=%s",
                entry_id,
                user_id,
            )

            entry = self.repo.get_entry(
                entry_id=entry_id,
                user_id=user_id,
            )

            logger.info(
                "Khata update repository lookup SUCCESS: entry_id=%s current_device=%s "
                "current_total_bill=%s current_cash=%s current_balance=%s",
                entry_id,
                getattr(entry, "device_id", None),
                getattr(entry, "total_bill", None),
                getattr(entry, "cash_received", None),
                getattr(entry, "balance", None),
            )

            clean_data = {k: v for k, v in data.items() if v is not None}

            # ---------------------------------------------------------
            # AUTO-FINALIZE LINKED MOTOR SESSION
            # ---------------------------------------------------------
            # If this Khata entry was created while the motor was running,
            # it starts with run_hours=0 and is_open=True. When an update
            # happens after MotorLog.end_time has been saved, use the
            # authoritative MotorLog timestamps to finalize the session.
            linked_motor_log_id = getattr(entry, "motor_log_id", None)

            if linked_motor_log_id:
                try:
                    linked_log = (
                        self.db.query(MotorLog)
                        .filter(
                            MotorLog.id == linked_motor_log_id,
                            MotorLog.device_id == entry.device_id,
                        )
                        .first()
                    )
                except SQLAlchemyError as exc:
                    _log_db_exception(
                        "Khata update linked motor log lookup",
                        exc,
                        entry_id=entry_id,
                        user_id=user_id,
                        motor_log_id=linked_motor_log_id,
                        device_id=getattr(entry, "device_id", None),
                    )
                    raise AppException(
                        status_code=500,
                        detail=f"Database error while finalizing motor session: {_db_error(exc)}",
                    )

                if (
                    linked_log
                    and linked_log.start_time
                    and linked_log.end_time
                ):
                    run_seconds = max(
                        0.0,
                        (
                            linked_log.end_time
                            - linked_log.start_time
                        ).total_seconds(),
                    )

                    clean_data["run_hours"] = round(
                        run_seconds / 3600,
                        2,
                    )
                    clean_data["started_at"] = linked_log.start_time
                    clean_data["ended_at"] = linked_log.end_time
                    clean_data["is_open"] = False

                    logger.info(
                        "Khata linked motor session FINALIZED: entry_id=%s "
                        "motor_log_id=%s start=%s end=%s run_seconds=%s "
                        "run_hours=%s is_open=%s",
                        entry_id,
                        linked_motor_log_id,
                        linked_log.start_time,
                        linked_log.end_time,
                        run_seconds,
                        clean_data["run_hours"],
                        clean_data["is_open"],
                    )

            logger.info(
                "Khata update clean payload: entry_id=%s fields=%s",
                entry_id,
                list(clean_data.keys()),
            )

            if "run_hours" in clean_data:
                clean_data["run_hours"] = round(_to_float(clean_data["run_hours"]), 2)
            if "price_per_hour" in clean_data:
                clean_data["price_per_hour"] = round(_to_float(clean_data["price_per_hour"]), 2)
            if "cash_received" in clean_data:
                clean_data["cash_received"] = round(_to_float(clean_data["cash_received"]), 2)

            logger.info(
                "Khata update repository write #1 START: entry_id=%s",
                entry_id,
            )
            updated = self.repo.update_entry(entry, clean_data)

            logger.info(
                "Khata update repository write #1 SUCCESS: entry_id=%s",
                entry_id,
            )

            run_hours = _to_float(updated.run_hours)
            price_per_hour = _to_float(updated.price_per_hour)
            cash_received = _to_float(updated.cash_received)

            total_bill = round(run_hours * price_per_hour, 2)

            updated_is_open = bool(getattr(updated, "is_open", False))

            if updated_is_open:
                # While motor is running, rate/cash can be saved but the
                # final bill and cleared state remain provisional.
                advance_amount = 0
                balance = 0
                is_cleared = False

            elif total_bill <= 0 and price_per_hour <= 0:
                # Motor has stopped, but rate is not set yet.
                advance_amount = 0
                balance = 0
                is_cleared = False

            elif cash_received >= total_bill:
                advance_amount = round(cash_received - total_bill, 2)
                balance = 0
                is_cleared = True

            else:
                advance_amount = 0
                balance = round(total_bill - cash_received, 2)
                is_cleared = False

            logger.info(
                "Khata update recalculation: entry_id=%s run_hours=%s price_per_hour=%s "
                "cash_received=%s total_bill=%s balance=%s advance=%s is_cleared=%s",
                entry_id,
                run_hours,
                price_per_hour,
                cash_received,
                total_bill,
                balance,
                advance_amount,
                is_cleared,
            )

            updated = self.repo.update_entry(
                updated,
                {
                    "total_bill": total_bill,
                    "balance": balance,
                    "advance_amount": advance_amount,
                    "is_cleared": is_cleared,
                },
            )

            logger.info(
                "Khata update SUCCESS: entry_id=%s",
                entry_id,
            )

            return self._attach_computed_fields(updated)

        except NotFoundException:
            raise AppException(status_code=404, detail="Khata entry not found")
        
        except AppException:
            raise

        except SQLAlchemyError as exc:
            _log_db_exception(
                "Khata update database error",
                exc,
                entry_id=entry_id,
                user_id=user_id,
            )
            raise AppException(
                status_code=500,
                detail=f"Database error while updating Khata entry: {_db_error(exc)}",
            )

        except Exception as exc:
            logger.error(
                "Khata update unexpected error: entry_id=%s user_id=%s error_type=%s error=%s",
                entry_id, user_id, type(exc).__name__, str(exc), exc_info=True,
            )
            raise AppException(
                status_code=500,
                detail=f"Unexpected error while updating Khata entry: {type(exc).__name__}: {str(exc)}",
            )

    def update_payment(
        self,
        entry_id: str,
        user_id: UUID,
        cash_received: float,
    ) -> KhataEntry:
        try:
            if cash_received <= 0:
                raise AppException(status_code=400, detail="cash_received must be greater than 0")

            logger.info(
                "Khata payment repository lookup START: entry_id=%s user_id=%s cash_received=%s",
                entry_id,
                user_id,
                cash_received,
            )

            entry = self.repo.get_entry(entry_id=entry_id, user_id=user_id)

            if bool(getattr(entry, "is_open", False)):
                raise AppException(
                    status_code=400,
                    detail="Cannot add payment while the motor Khata session is still open. Stop/finalize the motor first.",
                )

            if _to_float(getattr(entry, "total_bill", 0)) <= 0:
                raise AppException(
                    status_code=400,
                    detail="Set the price per hour and calculate the bill before adding payment.",
                )

            logger.info(
                "Khata payment repository lookup SUCCESS: entry_id=%s current_cash=%s "
                "total_bill=%s balance=%s",
                entry_id,
                getattr(entry, "cash_received", None),
                getattr(entry, "total_bill", None),
                getattr(entry, "balance", None),
            )

            current_cash = _to_float(entry.cash_received)
            total_cash = round(current_cash + cash_received, 2)
            total_bill = _to_float(entry.total_bill)

            if total_cash >= total_bill:
                advance_amount = round(total_cash - total_bill, 2)
                balance = 0
                is_cleared = True
            else:
                advance_amount = 0
                balance = round(total_bill - total_cash, 2)
                is_cleared = False

            logger.info(
                "Khata payment calculation: entry_id=%s current_cash=%s new_payment=%s "
                "total_cash=%s total_bill=%s balance=%s advance=%s is_cleared=%s",
                entry_id,
                current_cash,
                cash_received,
                total_cash,
                total_bill,
                balance,
                advance_amount,
                is_cleared,
            )

            updated = self.repo.update_entry(
                entry,
                {
                    "cash_received": total_cash,
                    "balance": balance,
                    "advance_amount": advance_amount,
                    "is_cleared": is_cleared,
                },
            )

            logger.info(
                "Payment added: entry=%s cash=%s balance=%s advance=%s",
                updated.id, updated.cash_received, updated.balance, updated.advance_amount,
            )

            logger.info(
                "Khata update FINAL SUCCESS: entry_id=%s user_id=%s total_bill=%s "
                "cash_received=%s balance=%s is_cleared=%s",
                entry_id,
                user_id,
                getattr(updated, "total_bill", None),
                getattr(updated, "cash_received", None),
                getattr(updated, "balance", None),
                getattr(updated, "is_cleared", None),
            )

            return self._attach_computed_fields(updated)

        except NotFoundException:
            logger.warning(
                "Khata update NOT FOUND: entry_id=%s user_id=%s",
                entry_id,
                user_id,
            )
            raise AppException(status_code=404, detail="Khata entry not found")

        except AppException:
            raise

        except SQLAlchemyError as exc:
            _log_db_exception(
                "Khata payment database error",
                exc,
                entry_id=entry_id,
                user_id=user_id,
            )
            raise AppException(
                status_code=500,
                detail=f"Database error while recording payment: {_db_error(exc)}",
            )

        except Exception as exc:
            logger.error(
                "Khata payment unexpected error: entry_id=%s user_id=%s error_type=%s error=%s",
                entry_id, user_id, type(exc).__name__, str(exc), exc_info=True,
            )
            raise AppException(
                status_code=500,
                detail=f"Unexpected error while recording payment: {type(exc).__name__}: {str(exc)}",
            )
   
    def delete_entry(self, entry_id: str, user_id: str) -> bool:
        """
        Delete a Khata entry.

        Rule:
        Closed Khata entries may be deleted by their owner.
        Active/open motor sessions cannot be deleted.
        """
        try:
            logger.info(
                "Khata delete repository lookup START: entry_id=%s user_id=%s",
                entry_id,
                user_id,
            )

            entry = self.repo.get_entry(entry_id=entry_id, user_id=user_id)

            logger.info(
                "Khata delete repository lookup SUCCESS: entry_id=%s is_cleared=%s balance=%s",
                entry_id,
                getattr(entry, "is_cleared", None),
                getattr(entry, "balance", None),
            )

            if bool(getattr(entry, "is_open", False)):
                raise AppException(
                    status_code=400,
                    detail="Cannot delete an open motor Khata session. Stop and finalize the motor first.",
                )

            logger.info(
                "Khata delete repository write START: entry_id=%s",
                entry_id,
            )
            result = self.repo.delete_entry(entry)

            logger.info(
                "Khata delete repository write SUCCESS: entry_id=%s result=%s",
                entry_id,
                result,
            )

            logger.info(
                "Khata entry deleted: entry_id=%s user_id=%s",
                entry_id,
                user_id,
            )

            return result

        except NotFoundException:
            raise AppException(
                status_code=404,
                detail="Khata entry not found",
            )

        except AppException:
            raise

        except SQLAlchemyError as exc:
            _log_db_exception(
                "Khata delete database error",
                exc,
                entry_id=entry_id,
                user_id=user_id,
            )
            raise AppException(
                status_code=500,
                detail=f"Database error while deleting Khata entry: {_db_error(exc)}",
            )

        except Exception as exc:
            logger.error(
                "Khata delete unexpected error: entry_id=%s user_id=%s error_type=%s error=%s",
                entry_id,
                user_id,
                type(exc).__name__,
                str(exc),
                exc_info=True,
            )
            raise AppException(
                status_code=500,
                detail=f"Unexpected error while deleting Khata entry: {type(exc).__name__}: {str(exc)}",
            )