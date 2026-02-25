from pydantic import BaseModel


class PaginationParams(BaseModel):
    offset: int = 0
    limit: int = 20
    search: str | None = None


class PaginationMeta(BaseModel):
    offset: int
    limit: int
    total: int
    filtered_total: int
    total_pages: int
    filtered_total_pages: int
    current_page: int
    has_next: bool
    has_prev: bool
