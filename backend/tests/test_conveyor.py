import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.conveyor.db import Base, SessionLocal, init_db, make_engine
from app.conveyor.models import Application, Client
from app.main import app

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://alfa:alfa@localhost:5432/alfa_test")


def prepare_test_database():
    server_url, name = TEST_DATABASE_URL.rsplit("/", 1)
    admin = make_engine(
        f"{server_url}/postgres",
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 3},
    )
    try:
        with admin.connect() as connection:
            exists = connection.scalar(
                text("select 1 from pg_database where datname = :name"),
                {"name": name},
            )
            if not exists:
                connection.execute(text(f'create database "{name}"'))
    except OperationalError:
        return False
    finally:
        admin.dispose()
    return True


pytestmark = pytest.mark.skipif(
    not prepare_test_database(),
    reason=f"Postgres недоступен: {TEST_DATABASE_URL}",
)

client = TestClient(app)

CAFE = {"X-Client-Id": "demo_cafe"}
LOGISTICS = {"X-Client-Id": "demo_logistics"}


@pytest.fixture(autouse=True)
def database():
    engine = make_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    engine.dispose()

    engine = init_db(TEST_DATABASE_URL)
    yield
    engine.dispose()


def add_application(client_id):
    with SessionLocal() as session:
        application = Application(client_id=client_id, product_id="overdraft", amount=500_000)
        session.add(application)
        session.commit()
        return application.id


def test_demo_clients_seeded():
    clients = client.get("/clients").json()
    assert {c["id"] for c in clients} == {"demo_cafe", "demo_logistics", "demo_newbie"}
    assert {c["legal_form"] for c in clients} == {"ip", "ooo"}


def test_seeding_is_idempotent():
    init_db(TEST_DATABASE_URL).dispose()
    with SessionLocal() as session:
        assert session.query(Client).count() == 3


def test_me_requires_client_header():
    assert client.get("/me").status_code == 401


def test_me_unknown_client():
    assert client.get("/me", headers={"X-Client-Id": "nobody"}).status_code == 401


def test_me_returns_profile_with_assets():
    me = client.get("/me", headers=LOGISTICS).json()
    assert me["legal_form"] == "ooo"
    assert len(me["inn"]) == 10
    assert {a["kind"] for a in me["assets"]} == {"real_estate", "vehicle"}


def test_applications_empty_list():
    assert client.get("/applications", headers=CAFE).json() == []


def test_owner_sees_application():
    application_id = add_application("demo_cafe")
    assert client.get(f"/applications/{application_id}", headers=CAFE).status_code == 200
    assert [a["id"] for a in client.get("/applications", headers=CAFE).json()] == [application_id]


def test_foreign_application_is_not_found():
    application_id = add_application("demo_cafe")
    assert client.get(f"/applications/{application_id}", headers=LOGISTICS).status_code == 404
    assert client.get("/applications", headers=LOGISTICS).json() == []


def test_missing_application_is_not_found():
    assert client.get("/applications/999", headers=CAFE).status_code == 404
