from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def dedupe_by_key(values: list[T], key_fn: Callable[[T], str]) -> list[T]:
    deduped: dict[str, T] = {}
    for value in values:
        deduped[key_fn(value)] = value
    return list(deduped.values())


def compute_partial_sync_operations(
    *,
    existing: list[T],
    to_add: list[T],
    to_remove: list[T],
    key_fn: Callable[[T], str],
) -> tuple[list[T], list[T]]:
    existing_map = {key_fn(value): value for value in dedupe_by_key(existing, key_fn)}
    add_map = {key_fn(value): value for value in dedupe_by_key(to_add, key_fn)}
    remove_map = {key_fn(value): value for value in dedupe_by_key(to_remove, key_fn)}

    overlap_keys = set(add_map).intersection(remove_map)
    for overlap_key in overlap_keys:
        add_map.pop(overlap_key, None)
        remove_map.pop(overlap_key, None)

    add_operations = [value for key, value in add_map.items() if key not in existing_map]
    remove_operations = [value for key, value in remove_map.items() if key in existing_map]
    return add_operations, remove_operations


def compute_partial_sync_operations_from_existing_keys(
    *,
    existing_keys: set[str],
    to_add: list[T],
    to_remove: list[T],
    key_fn: Callable[[T], str],
) -> tuple[list[T], list[T]]:
    add_map = {key_fn(value): value for value in dedupe_by_key(to_add, key_fn)}
    remove_map = {key_fn(value): value for value in dedupe_by_key(to_remove, key_fn)}

    overlap_keys = set(add_map).intersection(remove_map)
    for overlap_key in overlap_keys:
        add_map.pop(overlap_key, None)
        remove_map.pop(overlap_key, None)

    add_operations = [value for key, value in add_map.items() if key not in existing_keys]
    remove_operations = [value for key, value in remove_map.items() if key in existing_keys]
    return add_operations, remove_operations


def apply_partial_sync_operations(
    *,
    existing: list[T],
    to_add: list[T],
    to_remove: list[T],
    key_fn: Callable[[T], str],
    apply_add: Callable[[T], None],
    apply_remove: Callable[[T], None],
) -> None:
    add_operations, remove_operations = compute_partial_sync_operations(
        existing=existing,
        to_add=to_add,
        to_remove=to_remove,
        key_fn=key_fn,
    )
    for value in remove_operations:
        apply_remove(value)
    for value in add_operations:
        apply_add(value)


def apply_partial_sync_operations_from_existing_keys(
    *,
    existing_keys: set[str],
    to_add: list[T],
    to_remove: list[T],
    key_fn: Callable[[T], str],
    apply_add: Callable[[T], None],
    apply_remove: Callable[[T], None],
) -> None:
    add_operations, remove_operations = compute_partial_sync_operations_from_existing_keys(
        existing_keys=existing_keys,
        to_add=to_add,
        to_remove=to_remove,
        key_fn=key_fn,
    )
    for value in remove_operations:
        apply_remove(value)
    for value in add_operations:
        apply_add(value)
