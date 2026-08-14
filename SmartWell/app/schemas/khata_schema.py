# from datetime import date as DateType
# from typing import Optional, Literal
# from uuid import UUID

# from pydantic import (
#     BaseModel,
#     ConfigDict,
#     field_validator,
#     model_validator,
# )


# # ============================================================================
# # CREATE
# # ============================================================================

# class KhataCreate(BaseModel):
#     """
#     Input schema for creating a new Khata entry.

#     user_id is NOT accepted from request body.
#     It is taken from the authenticated JWT user.

#     price_per_hour may be 0 when the entry is automatically
#     created from motor stop. It can be updated later.

#     remaining_balance and payment_status are accepted for
#     backward compatibility but should be computed server-side.
#     """

#     customer_name: str
#     device_id: str

#     price_per_hour: float = 0.0

#     # MotorLog.id is UUID
#     motor_log_id: Optional[UUID] = None

#     cash_received: Optional[float] = 0.0

#     # Use DateType instead of date to avoid Pylance conflict
#     date: Optional[DateType] = None

#     run_hours: Optional[float] = None
#     total_bill: Optional[float] = 0.0
#     advance_amount: Optional[float] = 0.0

#     # Backward-compatible request fields.
#     # Server should calculate these.
#     remaining_balance: Optional[float] = None
#     payment_status: Optional[
#         Literal["paid", "partial", "unpaid"]
#     ] = None

#     # ------------------------------------------------------------------
#     # Validators
#     # ------------------------------------------------------------------

#     @field_validator("price_per_hour")
#     @classmethod
#     def price_not_negative(cls, value: float) -> float:
#         if value < 0:
#             raise ValueError("Price per hour cannot be negative")
#         return value

#     @field_validator("run_hours")
#     @classmethod
#     def run_hours_must_be_positive(
#         cls,
#         value: Optional[float],
#     ) -> Optional[float]:
#         if value is not None and value <= 0:
#             raise ValueError("run_hours must be greater than zero")
#         return value

#     @field_validator("total_bill")
#     @classmethod
#     def total_bill_not_negative(
#         cls,
#         value: Optional[float],
#     ) -> Optional[float]:
#         if value is not None and value < 0:
#             raise ValueError("total_bill cannot be negative")
#         return value

#     @field_validator("advance_amount")
#     @classmethod
#     def advance_not_negative(
#         cls,
#         value: Optional[float],
#     ) -> Optional[float]:
#         if value is not None and value < 0:
#             raise ValueError("Advance amount cannot be negative")
#         return value

#     @field_validator("cash_received")
#     @classmethod
#     def cash_not_negative(
#         cls,
#         value: Optional[float],
#     ) -> Optional[float]:
#         if value is not None and value < 0:
#             raise ValueError("Cash received cannot be negative")
#         return value

#     # ------------------------------------------------------------------
#     # Cross-field validation
#     # ------------------------------------------------------------------

#     @model_validator(mode="after")
#     def require_hours_source(self):
#         """
#         A Khata can be created using either:

#         1. run_hours directly
#         OR
#         2. motor_log_id from which run hours can be calculated.
#         """

#         if self.run_hours is None and self.motor_log_id is None:
#             raise ValueError(
#                 "Provide either 'run_hours' or 'motor_log_id'"
#             )

#         return self


# # ============================================================================
# # UPDATE
# # ============================================================================

# class KhataUpdate(BaseModel):
#     """
#     Update an existing Khata record.
#     """

#     customer_name: Optional[str] = None

#     run_hours: Optional[float] = None

#     price_per_hour: Optional[float] = None

#     total_bill: Optional[float] = None

#     cash_received: Optional[float] = None

#     date: Optional[DateType] = None

#     advance_amount: Optional[float] = None

#     # ------------------------------------------------------------------
#     # Validators
#     # ------------------------------------------------------------------

#     @field_validator("run_hours")
#     @classmethod
#     def run_hours_must_be_positive(
#         cls,
#         value: Optional[float],
#     ) -> Optional[float]:
#         if value is not None and value <= 0:
#             raise ValueError("run_hours must be greater than zero")
#         return value

#     @field_validator("price_per_hour", "total_bill")
#     @classmethod
#     def value_not_negative(
#         cls,
#         value: Optional[float],
#     ) -> Optional[float]:
#         if value is not None and value < 0:
#             raise ValueError("Value cannot be negative")
#         return value

#     @field_validator("cash_received")
#     @classmethod
#     def cash_not_negative(
#         cls,
#         value: Optional[float],
#     ) -> Optional[float]:
#         if value is not None and value < 0:
#             raise ValueError("Cash received cannot be negative")
#         return value

#     @field_validator("advance_amount")
#     @classmethod
#     def advance_not_negative(
#         cls,
#         value: Optional[float],
#     ) -> Optional[float]:
#         if value is not None and value < 0:
#             raise ValueError("Advance amount cannot be negative")
#         return value


# # ============================================================================
# # PAYMENT
# # ============================================================================

# class KhataPayment(BaseModel):
#     """
#     Add payment to an existing Khata record.
#     """

#     cash_received: float

#     @field_validator("cash_received")
#     @classmethod
#     def must_be_positive(cls, value: float) -> float:
#         if value <= 0:
#             raise ValueError(
#                 "Payment amount must be greater than zero"
#             )
#         return value


# # ============================================================================
# # RESPONSE
# # ============================================================================



# class KhataResponse(BaseModel):
#     id: UUID
#     user_id: UUID

#     customer_name: str
#     device_id: str

#     motor_log_id: Optional[UUID] = None

#     date: DateType
#     run_hours: float
#     price_per_hour: float

#     total_bill: float
#     cash_received: float
#     balance: float

#     advance_amount: float = 0
#     is_cleared: bool

#     remaining_balance: Optional[float] = None
#     payment_status: Optional[str] = None

#     model_config = ConfigDict(from_attributes=True)


from datetime import date as DateType, datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)


# ============================================================================
# CREATE
# ============================================================================

class KhataCreate(BaseModel):
    """
    Input schema for creating a new Khata entry.

    user_id is NOT accepted from request body.
    It is taken from the authenticated JWT user.

    price_per_hour may be 0 when the entry is automatically
    created for a running motor session. It can be updated later.

    A motor session may initially have:
    - motor_log_id = valid UUID
    - run_hours = 0
    because the motor is still running.

    remaining_balance and payment_status are accepted for
    backward compatibility but should be computed server-side.
    """

    customer_name: str
    device_id: str

    price_per_hour: float = 0.0

    # MotorLog.id is UUID
    motor_log_id: Optional[UUID] = None

    cash_received: Optional[float] = 0.0

    # Use DateType instead of date to avoid Pylance conflict
    date: Optional[DateType] = None

    run_hours: Optional[float] = None
    total_bill: Optional[float] = 0.0
    advance_amount: Optional[float] = 0.0

    # Backward-compatible request fields.
    # Server should calculate these.
    remaining_balance: Optional[float] = None

    payment_status: Optional[
        Literal["paid", "partial", "unpaid"]
    ] = None

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("price_per_hour")
    @classmethod
    def price_not_negative(
        cls,
        value: float,
    ) -> float:
        if value < 0:
            raise ValueError(
                "Price per hour cannot be negative"
            )

        return value

    @field_validator("run_hours")
    @classmethod
    def run_hours_not_negative(
        cls,
        value: Optional[float],
    ) -> Optional[float]:
        """
        run_hours = 0 is allowed for an active motor session.

        Negative runtime is never valid.
        """

        if value is not None and value < 0:
            raise ValueError(
                "run_hours cannot be negative"
            )

        return value

    @field_validator("total_bill")
    @classmethod
    def total_bill_not_negative(
        cls,
        value: Optional[float],
    ) -> Optional[float]:
        if value is not None and value < 0:
            raise ValueError(
                "total_bill cannot be negative"
            )

        return value

    @field_validator("advance_amount")
    @classmethod
    def advance_not_negative(
        cls,
        value: Optional[float],
    ) -> Optional[float]:
        if value is not None and value < 0:
            raise ValueError(
                "Advance amount cannot be negative"
            )

        return value

    @field_validator("cash_received")
    @classmethod
    def cash_not_negative(
        cls,
        value: Optional[float],
    ) -> Optional[float]:
        if value is not None and value < 0:
            raise ValueError(
                "Cash received cannot be negative"
            )

        return value

    # ------------------------------------------------------------------
    # Cross-field validation
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def require_hours_source(self):
        """
        A Khata can be created using either:

        1. run_hours directly for a manual/completed entry

        OR

        2. motor_log_id for a motor session.

        When motor_log_id exists, run_hours may be 0 because
        the motor may still be running.
        """

        # Motor session:
        # MotorLog provides the authoritative start/end times.
        if self.motor_log_id is not None:
            return self

        # Manual Khata:
        # Must have an actual positive duration.
        if self.run_hours is None or self.run_hours <= 0:
            raise ValueError(
                "Provide motor_log_id or run_hours greater than zero"
            )

        return self


# ============================================================================
# UPDATE
# ============================================================================

class KhataUpdate(BaseModel):
    """
    Update an existing Khata record.

    run_hours = 0 is allowed temporarily for an open motor session.
    Final run_hours should be calculated from MotorLog start/end time.
    """

    customer_name: Optional[str] = None

    run_hours: Optional[float] = None

    price_per_hour: Optional[float] = None

    total_bill: Optional[float] = None

    cash_received: Optional[float] = None

    date: Optional[DateType] = None

    advance_amount: Optional[float] = None

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("run_hours")
    @classmethod
    def run_hours_not_negative(
        cls,
        value: Optional[float],
    ) -> Optional[float]:
        """
        0 is allowed while a motor session is open.
        """

        if value is not None and value < 0:
            raise ValueError(
                "run_hours cannot be negative"
            )

        return value

    @field_validator(
        "price_per_hour",
        "total_bill",
    )
    @classmethod
    def value_not_negative(
        cls,
        value: Optional[float],
    ) -> Optional[float]:
        if value is not None and value < 0:
            raise ValueError(
                "Value cannot be negative"
            )

        return value

    @field_validator("cash_received")
    @classmethod
    def cash_not_negative(
        cls,
        value: Optional[float],
    ) -> Optional[float]:
        if value is not None and value < 0:
            raise ValueError(
                "Cash received cannot be negative"
            )

        return value

    @field_validator("advance_amount")
    @classmethod
    def advance_not_negative(
        cls,
        value: Optional[float],
    ) -> Optional[float]:
        if value is not None and value < 0:
            raise ValueError(
                "Advance amount cannot be negative"
            )

        return value


# ============================================================================
# PAYMENT
# ============================================================================

class KhataPayment(BaseModel):
    """
    Add payment to an existing Khata record.
    """

    cash_received: float

    @field_validator("cash_received")
    @classmethod
    def must_be_positive(
        cls,
        value: float,
    ) -> float:
        if value <= 0:
            raise ValueError(
                "Payment amount must be greater than zero"
            )

        return value


# ============================================================================
# RESPONSE
# ============================================================================

class KhataResponse(BaseModel):
    id: UUID
    user_id: UUID

    customer_name: str
    device_id: str

    motor_log_id: Optional[UUID] = None

    date: DateType

    run_hours: float
    price_per_hour: float

    total_bill: float
    cash_received: float
    balance: float

    advance_amount: float = 0

    is_cleared: bool

    remaining_balance: Optional[float] = None

    payment_status: Optional[str] = None

    # ------------------------------------------------------------------
    # MOTOR SESSION
    # ------------------------------------------------------------------

    # Original motor ON time.
    started_at: Optional[datetime] = None

    # Actual VFD-confirmed OFF time.
    ended_at: Optional[datetime] = None

    # True while motor session is still running.
    is_open: bool = False

    model_config = ConfigDict(
        from_attributes=True
    )