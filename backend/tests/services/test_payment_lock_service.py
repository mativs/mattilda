import pytest

from app.application.errors import ConflictError
from app.application.services.payment_lock_service import payment_creation_lock, payment_lock_key


def test_payment_lock_key_formats_scope():
    """
    Validate payment lock key includes school and invoice scope.

    1. Build lock key for one school and invoice pair.
    2. Read key string result.
    3. Validate expected prefix is present.
    4. Validate school and invoice ids are embedded.
    """

    key = payment_lock_key(school_id=5, invoice_id=42)
    assert key == "payment_lock:5:42"


def test_payment_creation_lock_acquires_and_releases(monkeypatch):
    """
    Validate payment creation lock acquires and releases lock token.

    1. Mock acquire_lock to return deterministic token.
    2. Enter and exit payment_creation_lock context once.
    3. Capture release_lock arguments.
    4. Validate release receives same scoped key and token.
    """

    released = {"key": None, "token": None}
    monkeypatch.setattr("app.application.services.payment_lock_service.acquire_lock", lambda *_args: "token-123")
    monkeypatch.setattr(
        "app.application.services.payment_lock_service.release_lock",
        lambda key, token: released.update(key=key, token=token),
    )
    with payment_creation_lock(school_id=3, invoice_id=8):
        pass
    assert released["key"] == "payment_lock:3:8"
    assert released["token"] == "token-123"


def test_payment_creation_lock_raises_conflict_when_not_acquired(monkeypatch):
    """
    Validate payment creation lock raises conflict on lock contention.

    1. Mock acquire_lock to return None.
    2. Enter payment_creation_lock context once.
    3. Validate ConflictError is raised.
    4. Validate message indicates lock contention.
    """

    monkeypatch.setattr("app.application.services.payment_lock_service.acquire_lock", lambda *_args: None)
    with pytest.raises(ConflictError) as exc:
        with payment_creation_lock(school_id=10, invoice_id=11):
            pass
    assert str(exc.value) == "A payment is already being processed for this invoice"
