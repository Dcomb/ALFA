import os

from sqlalchemy import create_engine
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

    with SessionLocal() as session:
        seed_demo_clients(session)

    return engine


def get_session():
    with SessionLocal() as session:
        yield session
