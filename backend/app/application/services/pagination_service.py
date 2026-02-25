from math import ceil
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.interfaces.api.v1.schemas.pagination import PaginationMeta


def apply_search_filter(query: Select, search: str | None, search_columns: list[Any]) -> Select:
    if search is None or not search_columns:
        return query
    pattern = f"%{search}%"
    conditions = [column.ilike(pattern) for column in search_columns]
    return query.where(or_(*conditions))


def paginate_scalars(
    db: Session,
    base_query: Select,
    *,
    offset: int,
    limit: int,
    search: str | None,
    search_columns: list[Any],
) -> tuple[list[Any], PaginationMeta]:
    filtered_query = apply_search_filter(base_query, search, search_columns)

    total = db.execute(select(func.count()).select_from(base_query.order_by(None).subquery())).scalar_one()
    filtered_total = db.execute(select(func.count()).select_from(filtered_query.order_by(None).subquery())).scalar_one()

    paged_query = filtered_query.offset(offset).limit(limit)
    items = list(db.execute(paged_query).scalars().all())

    total_pages = ceil(total / limit) if total > 0 else 0
    filtered_total_pages = ceil(filtered_total / limit) if filtered_total > 0 else 0
    current_page = (offset // limit) + 1 if filtered_total > 0 else 0

    meta = PaginationMeta(
        offset=offset,
        limit=limit,
        total=total,
        filtered_total=filtered_total,
        total_pages=total_pages,
        filtered_total_pages=filtered_total_pages,
        current_page=current_page,
        has_next=(offset + limit) < filtered_total,
        has_prev=offset > 0,
    )
    return items, meta
