from sqlalchemy import select

from app.application.services.pagination_service import paginate_scalars
from app.infrastructure.db.models import School
from tests.helpers.factories import create_school


def test_paginate_scalars_returns_totals_without_search(db_session):
    """
    Validate paginate_scalars count metadata without search.

    1. Seed three schools in database.
    2. Call paginate_scalars with offset zero and limit two.
    3. Validate first page item count follows limit.
    4. Validate total and filtered_total are identical.
    """
    create_school(db_session, "Page One", "page-one")
    create_school(db_session, "Page Two", "page-two")
    create_school(db_session, "Page Three", "page-three")
    items, meta = paginate_scalars(
        db=db_session,
        base_query=select(School).where(School.deleted_at.is_(None)).order_by(School.id),
        offset=0,
        limit=2,
        search=None,
        search_columns=[School.name, School.slug],
    )
    assert len(items) == 2
    assert meta.total == 3
    assert meta.filtered_total == 3
    assert meta.has_next is True


def test_paginate_scalars_applies_search_to_configured_columns(db_session):
    """
    Validate paginate_scalars declarative search behavior.

    1. Seed one matching and one non-matching school.
    2. Call paginate_scalars with search term once.
    3. Validate only matching school is returned.
    4. Validate filtered_total reflects search subset.
    """
    create_school(db_session, "Needle Academy", "needle-academy")
    create_school(db_session, "Other Academy", "other-academy")
    items, meta = paginate_scalars(
        db=db_session,
        base_query=select(School).where(School.deleted_at.is_(None)).order_by(School.id),
        offset=0,
        limit=10,
        search="needle",
        search_columns=[School.name, School.slug],
    )
    assert len(items) == 1
    assert items[0].slug == "needle-academy"
    assert meta.total == 2
    assert meta.filtered_total == 1


def test_paginate_scalars_sets_navigation_flags_for_middle_page(db_session):
    """
    Validate paginate_scalars page navigation metadata.

    1. Seed three schools in database.
    2. Call paginate_scalars requesting second page with limit one.
    3. Validate has_prev and has_next are both true.
    4. Validate current_page and filtered_total_pages values.
    """
    create_school(db_session, "One", "school-one")
    create_school(db_session, "Two", "school-two")
    create_school(db_session, "Three", "school-three")
    _, meta = paginate_scalars(
        db=db_session,
        base_query=select(School).where(School.deleted_at.is_(None)).order_by(School.id),
        offset=1,
        limit=1,
        search=None,
        search_columns=[School.name],
    )
    assert meta.has_prev is True
    assert meta.has_next is True
    assert meta.current_page == 2
    assert meta.filtered_total_pages == 3
