import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


SessionLocal = sessionmaker(expire_on_commit=False)


def make_engine(url, **kwargs):
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url, pool_pre_ping=True, **kwargs)


def init_db(url=None):
    from .demo import seed_demo_clients

    engine = make_engine(url or os.environ["DATABASE_URL"])
    SessionLocal.configure(bind=engine)
    Base.metadata.create_all(engine)
    _ensure_profile_and_snapshot_columns(engine)

    with SessionLocal() as session:
        seed_demo_clients(session)

    return engine


def _ensure_profile_and_snapshot_columns(engine):
    """Bring existing demo volumes forward without requiring Alembic."""
    columns = {
        "conveyor_clients": {
            "ogrn": "VARCHAR",
            "registration_date": "VARCHAR",
            "phone": "VARCHAR",
        },
        "conveyor_applications": {
            "client_snapshot": "JSON DEFAULT '{}'::json",
            "credit_snapshot": "JSON DEFAULT '{}'::json",
        },
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, definitions in columns.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, definition in definitions.items():
                if name not in existing:
                    connection.execute(text(
                        f'ALTER TABLE {table} ADD COLUMN {name} {definition}'
                    ))


def get_session():
    with SessionLocal() as session:
        yield session
