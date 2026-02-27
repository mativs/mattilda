from contextlib import contextmanager
from collections.abc import Iterator

from app.application.errors import ConflictError
from app.config import settings
from app.infrastructure.cache.cache_service import acquire_lock, release_lock


def payment_lock_key(*, school_id: int, invoice_id: int) -> str:
    return f"payment_lock:{school_id}:{invoice_id}"


@contextmanager
def payment_creation_lock(*, school_id: int, invoice_id: int) -> Iterator[None]:
    lock_key = payment_lock_key(school_id=school_id, invoice_id=invoice_id)
    lock_token = acquire_lock(lock_key, settings.payment_lock_ttl_seconds)
    if lock_token is None:
        raise ConflictError("A payment is already being processed for this invoice")
    try:
        yield
    finally:
        release_lock(lock_key, lock_token)
