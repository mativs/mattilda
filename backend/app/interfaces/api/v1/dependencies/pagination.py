from fastapi import Query

from app.interfaces.api.v1.schemas.pagination import PaginationParams


def get_pagination_params(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
) -> PaginationParams:
    normalized_search = search.strip() if search is not None else None
    if normalized_search == "":
        normalized_search = None
    return PaginationParams(offset=offset, limit=limit, search=normalized_search)
