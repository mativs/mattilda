from sqlalchemy import text
from sqlalchemy.orm import Session


def prepare_rls_tester(db: Session) -> None:
    db.execute(text("DROP ROLE IF EXISTS rls_tester"))
    db.execute(text("CREATE ROLE rls_tester LOGIN PASSWORD 'rls_tester'"))
    db.execute(text("GRANT USAGE ON SCHEMA public TO rls_tester"))
    db.execute(text("GRANT SELECT ON dummy_records TO rls_tester"))
    db.commit()


def read_dummy_records_for_school(db: Session, school_id: int) -> list[str]:
    connection = db.get_bind().connect()
    try:
        connection.execute(text("SET ROLE rls_tester"))
        connection.execute(
            text("SELECT set_config('app.current_school_id', :school_id, false)"),
            {"school_id": str(school_id)},
        )
        rows = connection.execute(text("SELECT name FROM dummy_records ORDER BY name")).all()
        return [row[0] for row in rows]
    finally:
        connection.close()
