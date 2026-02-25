from app.application.services.association_sync_service import (
    apply_partial_sync_operations,
    compute_partial_sync_operations,
)


def test_compute_partial_sync_operations_dedupes_and_filters_by_existing():
    """
    Validate compute_partial_sync_operations dedupe and filtering behavior.

    1. Build existing, add, and remove inputs with duplicates.
    2. Call compute_partial_sync_operations once.
    3. Validate add operations exclude already-existing entries.
    4. Validate remove operations include only existing entries.
    """
    existing = ["a", "b"]
    to_add = ["b", "c", "c"]
    to_remove = ["x", "a", "a"]
    add_ops, remove_ops = compute_partial_sync_operations(
        existing=existing,
        to_add=to_add,
        to_remove=to_remove,
        key_fn=lambda value: value,
    )
    assert sorted(add_ops) == ["c"]
    assert sorted(remove_ops) == ["a"]


def test_compute_partial_sync_operations_drops_overlap_between_add_and_remove():
    """
    Validate compute_partial_sync_operations overlap resolution.

    1. Build add and remove inputs with same key.
    2. Call compute_partial_sync_operations once.
    3. Validate overlapping operation key is ignored.
    4. Validate resulting operations are empty for overlap-only case.
    """
    add_ops, remove_ops = compute_partial_sync_operations(
        existing=["a"],
        to_add=["a"],
        to_remove=["a"],
        key_fn=lambda value: value,
    )
    assert add_ops == []
    assert remove_ops == []


def test_apply_partial_sync_operations_executes_remove_then_add():
    """
    Validate apply_partial_sync_operations operation order.

    1. Build existing and target add/remove operations.
    2. Call apply_partial_sync_operations once.
    3. Capture callback execution sequence.
    4. Validate remove callback runs before add callback.
    """
    executed = []
    apply_partial_sync_operations(
        existing=["a"],
        to_add=["b"],
        to_remove=["a"],
        key_fn=lambda value: value,
        apply_add=lambda value: executed.append(f"add:{value}"),
        apply_remove=lambda value: executed.append(f"remove:{value}"),
    )
    assert executed == ["remove:a", "add:b"]
