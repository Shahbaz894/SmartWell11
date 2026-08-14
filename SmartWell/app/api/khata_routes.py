# app/api/khata_routes.py

"""
===============================================================================
KHATA / ACCOUNTING API ROUTES
===============================================================================

Purpose
-------
This router provides all API endpoints related to Khata (customer billing /
ledger) entries.

Base URL
--------
    /khata

Authentication
--------------
Every endpoint requires a valid JWT Bearer token through:

    get_current_user

Ownership / Security
--------------------
The authenticated user's ID is ALWAYS taken from the JWT.

The client is NOT allowed to send user_id in the request body and decide
which user's Khata entries should be accessed.

This prevents one user from reading, modifying, or deleting another user's
ledger entries.

Important UUID Handling
-----------------------
Depending on the SQLAlchemy User model configuration, current_user.id may be:

    uuid.UUID

while some Khata database columns / service methods may expect:

    str

Therefore we explicitly normalize the authenticated user's ID using:

    str(current_user.id)

before passing it to the service layer.

Architecture
------------
Request
   |
   v
FastAPI Router
   |
   +--> JWT Authentication
   |
   +--> Database Session
   |
   v
KhataService
   |
   v
KhataRepository
   |
   v
PostgreSQL

The router should mainly handle:
    - HTTP request/response
    - authentication dependencies
    - request validation
    - converting IDs to strings
    - calling the service layer

Business logic belongs in KhataService.
Database queries belong in KhataRepository.

===============================================================================
ENDPOINT SUMMARY
===============================================================================

GET
    /khata/me
        Debug/authentication endpoint.
        Returns authenticated user's ID and email.

POST
    /khata/
        Create a new Khata entry.

GET
    /khata/
        Return all Khata entries belonging to the authenticated user.

GET
    /khata/{entry_id}
        Return one Khata entry.

PATCH
    /khata/{entry_id}
        Update an existing Khata entry.

POST
    /khata/{entry_id}/payment
        Add a payment against an existing Khata entry.

DELETE
    /khata/{entry_id}
        Delete an entry after it has been completely cleared.

===============================================================================
"""

# =============================================================================
# IMPORTS
# =============================================================================

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.core.logger import logger

from app.schemas.khata_schema import (
    KhataCreate,
    KhataUpdate,
    KhataPayment,
    KhataResponse,
)

from app.services.khata_service import KhataService


# =============================================================================
# ROUTER CONFIGURATION
# =============================================================================

"""
All endpoints defined in this file automatically receive:

    /khata

as their URL prefix.

For example:

    @router.get("/")
becomes:

    GET /khata/

Tags:
    "Accounting"

This makes the endpoints appear under the Accounting section in Swagger.
"""

router = APIRouter(
    prefix="/khata",
    tags=["Accounting"],
)


# =============================================================================
# SERVICE DEPENDENCY
# =============================================================================

def _get_service(
    db: Session = Depends(get_db),
) -> KhataService:
    """
    Create a KhataService using the current database session.

    FastAPI automatically calls get_db() and injects the SQLAlchemy Session.

    Flow:

        HTTP request
             |
             v
        get_db()
             |
             v
        SQLAlchemy Session
             |
             v
        KhataService(db)

    Keeping service creation inside a dependency makes the route functions
    small and keeps database/session management centralized.
    """

    logger.debug(
        "Khata route: creating KhataService with db=%s",
        type(db).__name__,
    )

    return KhataService(db)


# =============================================================================
# DEBUG / AUTHENTICATION ENDPOINT
# =============================================================================

@router.get(
    "/me",
    summary="Return current authenticated user information",
    description=(
        "Debug endpoint used to verify the JWT token and identify "
        "the authenticated user."
    ),
)
def get_me(
    current_user=Depends(get_current_user),
):
    """
    Return information about the currently authenticated user.

    This endpoint does NOT access Khata records.

    It is useful for debugging authentication problems.

    Example response:

        {
            "user_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            "email": "user@example.com"
        }

    If this endpoint fails, the problem is probably related to:

        - JWT token
        - Authorization header
        - get_current_user()
        - User lookup

    If this endpoint works but GET /khata/ fails, authentication is probably
    working and the problem is further down the Khata request pipeline.
    """

    logger.info(
        "KHATA /me START: user_id=%r type=%s email=%r",
        getattr(current_user, "id", None),
        type(getattr(current_user, "id", None)).__name__,
        getattr(current_user, "email", None),
    )

    response = {
        "user_id": str(current_user.id),
        "email": current_user.email,
    }

    logger.info(
        "KHATA /me SUCCESS: user_id=%s",
        response["user_id"],
    )

    return response


# =============================================================================
# CREATE KHATA ENTRY
# =============================================================================

@router.post(
    "/",
    response_model=KhataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Khata entry",
    description=(
        "Create a billing/ledger entry for a water consumer. "
        "The authenticated user's ID is automatically assigned from "
        "the JWT token. user_id cannot be supplied by the client."
    ),
)
def create_entry(
    body: KhataCreate,

    current_user=Depends(get_current_user),

    service: KhataService = Depends(_get_service),
):
    """
    Create a new Khata entry.

    Request body contains billing information such as:

        - customer/device information
        - run hours
        - rate
        - payment information
        - other Khata fields

    Security
    --------
    user_id is NOT taken from body.

    Instead:

        current_user.id

    is obtained from the authenticated JWT.

    UUID Normalization
    ------------------
    current_user.id may be a uuid.UUID object.

    We explicitly convert it to:

        str(current_user.id)

    before passing it to the service layer.

    Business logic
    --------------
    KhataService is responsible for:

        - validating ownership
        - calculating run hours
        - calculating bill
        - calculating balance
        - determining cleared status
        - creating the database record
    """

    user_id = str(current_user.id)

    logger.info(
        "KHATA CREATE START: user_id=%s type=%s",
        user_id,
        type(current_user.id).__name__,
    )

    logger.debug(
        "KHATA CREATE BODY: %s",
        body.model_dump(),
    )

    result = service.create_entry(
        user_id=user_id,
        data=body.model_dump(),
    )

    logger.info(
        "KHATA CREATE SUCCESS: user_id=%s entry_id=%s",
        user_id,
        getattr(result, "id", None),
    )

    return result


# =============================================================================
# LIST ALL KHATA ENTRIES
# =============================================================================

@router.get(
    "/",
    response_model=list[KhataResponse],
    summary="List all Khata entries",
    description=(
        "Return all Khata entries belonging to the authenticated user, "
        "ordered from newest to oldest."
    ),
)
def get_all_entries(
    current_user=Depends(get_current_user),

    service: KhataService = Depends(_get_service),
):
    """
    Return every Khata entry belonging to the authenticated user.

    IMPORTANT
    ---------
    The client does not provide user_id.

    We always use:

        current_user.id

    from the JWT.

    This prevents:

        User A -> requesting User B's Khata records.

    UUID Normalization
    ------------------
    Convert:

        UUID object

    into:

        string

    before passing it to KhataService.

    Detailed logging is included here because this endpoint is the main
    endpoint used when the Flutter Khata screen loads.

    Request flow:

        Flutter
           |
           v
        GET /khata/
           |
           v
        JWT authentication
           |
           v
        current_user
           |
           v
        str(current_user.id)
           |
           v
        KhataService.get_all_entries()
           |
           v
        KhataRepository.get_all_entries()
           |
           v
        PostgreSQL
    """

    user_id = str(current_user.id)

    # -------------------------------------------------------------------------
    # LOG: ROUTE START
    # -------------------------------------------------------------------------

    logger.info(
        "KHATA GET_ALL ROUTE START: user_id=%s current_user_id_type=%s",
        user_id,
        type(current_user.id).__name__,
    )

    # -------------------------------------------------------------------------
    # CALL SERVICE
    # -------------------------------------------------------------------------

    try:

        result = service.get_all_entries(
            user_id=user_id,
        )

    except Exception:

        # Log the complete traceback.
        logger.exception(
            "KHATA GET_ALL ROUTE FAILED: user_id=%s",
            user_id,
        )

        raise

    # -------------------------------------------------------------------------
    # LOG: SUCCESS
    # -------------------------------------------------------------------------

    logger.info(
        "KHATA GET_ALL ROUTE SUCCESS: user_id=%s entries=%d",
        user_id,
        len(result),
    )

    return result


# =============================================================================
# GET SINGLE KHATA ENTRY
# =============================================================================

@router.get(
    "/{entry_id}",
    response_model=KhataResponse,
    summary="Get a single Khata entry",
    description=(
        "Return one Khata entry by ID. "
        "The entry must belong to the authenticated user."
    ),
)
def get_entry(
    entry_id: str,

    current_user=Depends(get_current_user),

    service: KhataService = Depends(_get_service),
):
    """
    Fetch one Khata entry.

    Security
    --------
    The repository/service must verify both:

        entry_id
        user_id

    This prevents a user from accessing another user's entry merely by
    knowing its UUID.
    """

    user_id = str(current_user.id)
    entry_id = str(entry_id)

    logger.info(
        "KHATA GET_ONE START: entry_id=%s user_id=%s",
        entry_id,
        user_id,
    )

    try:

        result = service.get_entry(
            entry_id=entry_id,
            user_id=user_id,
        )

    except Exception:

        logger.exception(
            "KHATA GET_ONE FAILED: entry_id=%s user_id=%s",
            entry_id,
            user_id,
        )

        raise

    logger.info(
        "KHATA GET_ONE SUCCESS: entry_id=%s user_id=%s",
        entry_id,
        user_id,
    )

    return result


# =============================================================================
# UPDATE KHATA ENTRY
# =============================================================================

@router.patch(
    "/{entry_id}",
    response_model=KhataResponse,
    summary="Update Khata entry fields",
    description=(
        "Partially update a Khata entry. "
        "The authenticated user's ownership is enforced."
    ),
)
def update_entry(
    entry_id: str,

    body: KhataUpdate,

    current_user=Depends(get_current_user),

    service: KhataService = Depends(_get_service),
):
    """
    Partially update an existing Khata entry.

    Only fields supplied in the request are updated.

    exclude_none=True prevents unspecified fields from overwriting existing
    database values with NULL.

    The service layer is responsible for recalculating:

        - balance
        - is_cleared
        - other derived billing values
    """

    user_id = str(current_user.id)
    entry_id = str(entry_id)

    update_data = body.model_dump(
        exclude_none=True,
    )

    logger.info(
        "KHATA UPDATE START: entry_id=%s user_id=%s fields=%s",
        entry_id,
        user_id,
        list(update_data.keys()),
    )

    try:

        result = service.update_entry(
            entry_id=entry_id,
            user_id=user_id,
            data=update_data,
        )

    except Exception:

        logger.exception(
            "KHATA UPDATE FAILED: entry_id=%s user_id=%s",
            entry_id,
            user_id,
        )

        raise

    logger.info(
        "KHATA UPDATE SUCCESS: entry_id=%s user_id=%s",
        entry_id,
        user_id,
    )

    return result


# =============================================================================
# PAYMENT
# =============================================================================

@router.post(
    "/{entry_id}/payment",
    response_model=KhataResponse,
    summary="Record a payment against a Khata entry",
    description=(
        "Add a payment to an existing Khata entry. "
        "The balance and cleared status are recalculated by the service."
    ),
)
def update_payment(
    entry_id: str,

    body: KhataPayment,

    current_user=Depends(get_current_user),

    service: KhataService = Depends(_get_service),
):
    """
    Record an additional payment.

    Example:

        Existing bill:
            5000

        Payment:
            2000

        Remaining balance:
            3000

    The service layer handles the actual calculation.

    Security
    --------
    The entry must belong to current_user.
    """

    user_id = str(current_user.id)
    entry_id = str(entry_id)

    logger.info(
        "KHATA PAYMENT START: entry_id=%s user_id=%s cash_received=%s",
        entry_id,
        user_id,
        body.cash_received,
    )

    try:

        result = service.update_payment(
            entry_id=entry_id,
            user_id=user_id,
            cash_received=body.cash_received,
        )

    except Exception:

        logger.exception(
            "KHATA PAYMENT FAILED: entry_id=%s user_id=%s",
            entry_id,
            user_id,
        )

        raise

    logger.info(
        "KHATA PAYMENT SUCCESS: entry_id=%s user_id=%s",
        entry_id,
        user_id,
    )

    return result


# =============================================================================
# DELETE KHATA ENTRY
# =============================================================================

@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a cleared Khata entry",
    description=(
        "Permanently delete a Khata entry. "
        "Deletion is allowed only after the entry has been fully cleared."
    ),
)
def delete_entry(
    entry_id: str,

    current_user=Depends(get_current_user),

    service: KhataService = Depends(_get_service),
):
    """
    Delete a Khata entry.

    The service layer should enforce:

        balance == 0
        OR
        is_cleared == True

    before allowing deletion.

    Ownership is also checked using:

        entry_id
        authenticated user_id
    """

    user_id = str(current_user.id)
    entry_id = str(entry_id)

    logger.info(
        "KHATA DELETE START: entry_id=%s user_id=%s",
        entry_id,
        user_id,
    )

    try:

        service.delete_entry(
            entry_id=entry_id,
            user_id=user_id,
        )

    except Exception:

        logger.exception(
            "KHATA DELETE FAILED: entry_id=%s user_id=%s",
            entry_id,
            user_id,
        )

        raise

    logger.info(
        "KHATA DELETE SUCCESS: entry_id=%s user_id=%s",
        entry_id,
        user_id,
    )

    return {
        "detail": "Entry successfully deleted",
        "entry_id": entry_id,
    }