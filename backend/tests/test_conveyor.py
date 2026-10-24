import os

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.conveyor import sources
from app.conveyor.db import Base, SessionLocal, init_db, make_engine
from app.conveyor.demo import DEMO_CLIENTS
from app.conveyor.models import Application, Client
from app.main import app
from app.scoring.inference import MODEL_VERSION

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


FAILURES = {}
CALLS = []
OVERRIDES = {}

WORLD = {
    "egrul": {"legal_form": "IP", "registry_status": "active", "registration_date": "2024-01-15"},
    "fns": {"disqualified_person_flag": 0, "tax_arrears_flag": 0, "mass_address_flag": 0, "court_cases_12m": 0},
    "girbo": {"total_assets": 10000000},
    "bank": {"avg_monthly_account_turnover": 1200000},
    "bki": {"existing_monthly_payment": 0, "current_overdue_days": 0},
}


def fake_external(request):
    source = request.url.path.split("/")[1]
    CALLS.append(source)
    behavior = FAILURES.get(source)

    if behavior == "error":
        return httpx.Response(503)
    if behavior == "timeout":
        raise httpx.ReadTimeout("timeout", request=request)
    if behavior == "missing":
        return httpx.Response(404)
    if behavior == "flaky" and CALLS.count(source) == 1:
        return httpx.Response(503)

    return httpx.Response(200, json={**WORLD[source], **OVERRIDES.get(source, {})})


@pytest.fixture(autouse=True)
def external(monkeypatch):
    FAILURES.clear()
    CALLS.clear()
    OVERRIDES.clear()
    monkeypatch.setattr(sources, "transport", httpx.MockTransport(fake_external))
    monkeypatch.setattr(sources, "BACKOFF", 0)


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
        application = Application(client_id=client_id, product_id="overdraft", amount=500000)
        session.add(application)
        session.commit()
        return application.id


def test_demo_clients_seeded():
    clients = client.get("/clients").json()
    assert {c["id"] for c in clients} == {c["id"] for c in DEMO_CLIENTS}
    assert {c["legal_form"] for c in clients} == {"ip", "ooo"}


def test_seeding_is_idempotent():
    init_db(TEST_DATABASE_URL).dispose()
    with SessionLocal() as session:
        assert session.query(Client).count() == len(DEMO_CLIENTS)


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


FULL_DRAFT = {
    "product_id": "loan_any_purpose",
    "amount": 1000000,
    "term_months": 24,
    "purpose": "working_capital",
    "declared_revenue": 1200000,
    "declared_expenses": 950000,
    "bki_consent": True,
}


def create(headers=CAFE, **fields):
    response = client.post("/applications", json={**FULL_DRAFT, **fields}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def statuses(application):
    return [(h["from_status"], h["to_status"], h["actor"]) for h in application["history"]]


def test_create_draft():
    application = create()
    assert application["status"] == "draft"
    assert statuses(application) == [(None, "draft", "client")]


def test_create_requires_product():
    assert client.post("/applications", json={}, headers=CAFE).status_code == 422


def test_create_unknown_product():
    response = client.post("/applications", json={"product_id": "nope"}, headers=CAFE)
    assert response.status_code == 422


def test_create_rejects_unknown_field():
    response = client.post("/applications", json={"product_id": "overdraft", "rate": 1}, headers=CAFE)
    assert response.status_code == 422


def test_collateral_must_belong_to_client():
    logistics_asset = client.get("/me", headers=LOGISTICS).json()["assets"][0]["id"]
    response = client.post(
        "/applications",
        json={"product_id": "loan_secured", "collateral_asset_id": logistics_asset},
        headers=CAFE,
    )
    assert response.status_code == 422
    create(headers=LOGISTICS, product_id="loan_secured", collateral_asset_id=logistics_asset, applicant_role="director")


def test_update_draft():
    application = create()
    response = client.patch(f"/applications/{application['id']}", json={"amount": 750000}, headers=CAFE)
    assert response.status_code == 200
    assert response.json()["amount"] == 750000
    assert response.json()["term_months"] == 24


def test_submit_complete_draft():
    application = create()
    response = client.post(f"/applications/{application['id']}/submit", headers=CAFE)
    assert response.status_code == 200
    assert statuses(response.json())[1:] == [
        ("draft", "submitted", "client"),
        ("submitted", "checking", "system"),
        ("checking", "scoring", "system"),
        ("scoring", "approved", "system"),
    ]


def test_submit_incomplete_lists_missing():
    response = client.post("/applications", json={"product_id": "overdraft"}, headers=CAFE)
    application_id = response.json()["id"]
    response = client.post(f"/applications/{application_id}/submit", headers=CAFE)
    assert response.status_code == 422
    assert "сумма" in response.json()["missing"]
    assert "согласие на запрос в БКИ" in response.json()["missing"]


def test_ooo_requires_applicant_role_ip_does_not():
    ooo = create(headers=LOGISTICS)
    response = client.post(f"/applications/{ooo['id']}/submit", headers=LOGISTICS)
    assert response.status_code == 422
    assert response.json()["missing"] == ["роль заявителя"]

    ip = create()
    assert client.post(f"/applications/{ip['id']}/submit", headers=CAFE).status_code == 200


def test_submitted_application_cannot_be_edited():
    application = create()
    client.post(f"/applications/{application['id']}/submit", headers=CAFE)
    response = client.patch(f"/applications/{application['id']}", json={"amount": 1}, headers=CAFE)
    assert response.status_code == 409


def test_double_submit_is_conflict():
    application = create()
    assert client.post(f"/applications/{application['id']}/submit", headers=CAFE).status_code == 200
    assert client.post(f"/applications/{application['id']}/submit", headers=CAFE).status_code == 409


def test_parallel_submit_succeeds_once():
    from concurrent.futures import ThreadPoolExecutor

    application = create()
    url = f"/applications/{application['id']}/submit"
    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = sorted(pool.map(lambda _: client.post(url, headers=CAFE).status_code, range(4)))
    assert codes == [200, 409, 409, 409]

    history = client.get(f"/applications/{application['id']}", headers=CAFE).json()["history"]
    assert [h["to_status"] for h in history] == ["draft", "submitted", "checking", "scoring", "approved"]


def test_withdraw():
    draft = create()
    response = client.post(f"/applications/{draft['id']}/withdraw", headers=CAFE)
    assert response.json()["status"] == "withdrawn"

    processed = create()
    client.post(f"/applications/{processed['id']}/submit", headers=CAFE)
    assert client.post(f"/applications/{processed['id']}/withdraw", headers=CAFE).status_code == 409


def test_withdrawn_is_final():
    application = create()
    client.post(f"/applications/{application['id']}/withdraw", headers=CAFE)
    assert client.post(f"/applications/{application['id']}/withdraw", headers=CAFE).status_code == 409
    assert client.post(f"/applications/{application['id']}/submit", headers=CAFE).status_code == 409


def test_foreign_client_cannot_act():
    application = create()
    application_id = application["id"]
    assert client.patch(f"/applications/{application_id}", json={"amount": 1}, headers=LOGISTICS).status_code == 404
    assert client.post(f"/applications/{application_id}/submit", headers=LOGISTICS).status_code == 404
    assert client.post(f"/applications/{application_id}/withdraw", headers=LOGISTICS).status_code == 404


def test_client_cannot_do_system_transitions():
    from app.conveyor.lifecycle import NotAllowed, transition

    with SessionLocal() as session:
        application = session.get(Application, create()["id"])
        application.status = "submitted"
        with pytest.raises(NotAllowed):
            transition(session, application, "checking", "client")
        with pytest.raises(NotAllowed):
            transition(session, application, "approved", "system")


def submit(headers=CAFE, **fields):
    application = create(headers=headers, **fields)
    response = client.post(f"/applications/{application['id']}/submit", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def source_statuses(application):
    return {s["source"]: s["status"] for s in application["sources"]}


def test_submit_fetches_all_sources():
    application = submit()
    assert application["status"] == "approved"
    assert source_statuses(application) == {source: "ok" for source in sources.SOURCES}


def test_failed_source_keeps_application_in_checking():
    FAILURES["bki"] = "error"
    application = submit()
    assert application["status"] == "checking"
    assert source_statuses(application)["bki"] == "error"
    assert CALLS.count("bki") == 1 + sources.RETRIES


def test_retry_fetches_only_failed_sources():
    FAILURES["bki"] = "error"
    application = submit()
    FAILURES.clear()
    CALLS.clear()

    response = client.post(f"/applications/{application['id']}/process", headers=CAFE)
    assert response.status_code == 200
    assert CALLS == ["bki"]
    bki = [s["status"] for s in response.json()["sources"] if s["source"] == "bki"]
    assert bki == ["error", "ok"]
    assert response.json()["status"] == "approved"


def test_timeout_is_recorded():
    FAILURES["egrul"] = "timeout"
    application = submit()
    assert source_statuses(application)["egrul"] == "timeout"


def test_transient_failure_is_retried():
    FAILURES["bank"] = "flaky"
    application = submit()
    assert source_statuses(application)["bank"] == "ok"
    assert CALLS.count("bank") == 2


def test_not_found_is_final_answer():
    FAILURES["girbo"] = "missing"
    application = submit()
    assert source_statuses(application)["girbo"] == "not_found"
    assert CALLS.count("girbo") == 1

    CALLS.clear()
    client.post(f"/applications/{application['id']}/process", headers=CAFE)
    assert CALLS == []


def test_process_only_in_checking():
    application = create()
    assert client.post(f"/applications/{application['id']}/process", headers=CAFE).status_code == 409


def resubmit(application_id, headers=CAFE, **fields):
    if fields:
        response = client.patch(f"/applications/{application_id}", json=fields, headers=headers)
        assert response.status_code == 200, response.text
    response = client.post(f"/applications/{application_id}/submit", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def check_codes(application_id, headers=CAFE):
    processing = client.get(f"/applications/{application_id}/processing", headers=headers).json()
    return [c["code"] for c in processing["checks"]]


def test_clean_application_is_approved():
    application = submit()
    assert application["status"] == "approved"
    assert application["issues"] == []
    codes = check_codes(application["id"])
    assert {"business_age", "fns_flags", "debt_from_bki", "revenue_confirmed"} <= set(codes)


def test_company_not_in_registry_is_declined():
    FAILURES["egrul"] = "missing"
    application = submit()
    assert application["status"] == "declined"
    assert "не найдена в госреестре" in application["issues"][0]


def test_liquidated_company_is_declined():
    OVERRIDES["egrul"] = {"registry_status": "liquidated"}
    application = submit()
    assert application["status"] == "declined"
    assert statuses(application)[-1] == ("checking", "declined", "system")


def test_current_overdue_is_declined():
    OVERRIDES["bki"] = {"current_overdue_days": 45}
    application = submit()
    assert application["status"] == "declined"
    assert "45" in application["issues"][0]


def test_small_overdue_is_not_stop_factor():
    OVERRIDES["bki"] = {"current_overdue_days": 10}
    assert submit()["status"] != "declined"


def test_disqualified_director_declines_only_ooo():
    OVERRIDES["fns"] = {"disqualified_person_flag": 1}
    assert submit(headers=CAFE)["status"] == "approved"
    ooo = submit(headers=LOGISTICS, applicant_role="director")
    assert ooo["status"] == "declined"
    assert "дисквалифицирован" in ooo["issues"][0]


def test_revenue_above_turnover_needs_info():
    OVERRIDES["bank"] = {"avg_monthly_account_turnover": 500000}
    application = submit()
    assert application["status"] == "needs_info"
    assert application["info_rounds"] == 1
    assert "уточните выручку" in application["issues"][0]


def test_corrected_revenue_passes_without_refetching_sources():
    OVERRIDES["bank"] = {"avg_monthly_account_turnover": 500000}
    application = submit()
    CALLS.clear()

    corrected = resubmit(application["id"], declared_revenue=600000, declared_expenses=450000)
    assert corrected["status"] in {"approved", "counteroffer"}
    assert corrected["issues"] == []
    assert CALLS == []


def test_third_failed_round_is_declined():
    OVERRIDES["bank"] = {"avg_monthly_account_turnover": 500000}
    application = submit()
    assert resubmit(application["id"])["status"] == "needs_info"

    final = resubmit(application["id"])
    assert final["status"] == "declined"
    assert final["info_rounds"] == 2
    assert final["history"][-1]["reason"].startswith("не удалось подтвердить данные")


def test_hidden_debt_needs_info():
    OVERRIDES["bki"] = {"existing_monthly_payment": 300000}
    application = submit(declared_debt_payment=100000)
    assert application["status"] == "needs_info"
    assert "БКИ" in application["issues"][0]


def test_debt_taken_from_bki_when_not_declared():
    OVERRIDES["bki"] = {"existing_monthly_payment": 300000}
    application = submit()
    assert "debt_from_bki" in check_codes(application["id"])
    assert application["status"] == "declined"
    assert "по денежному потоку" in application["decision"]["reasons"][0]


def test_withdraw_from_needs_info():
    OVERRIDES["bank"] = {"avg_monthly_account_turnover": 500000}
    application = submit()
    response = client.post(f"/applications/{application['id']}/withdraw", headers=CAFE)
    assert response.json()["status"] == "withdrawn"


def test_processing_journal():
    application = submit()
    processing = client.get(f"/applications/{application['id']}/processing", headers=CAFE).json()

    assert [h["to_status"] for h in processing["history"]] == ["draft", "submitted", "checking", "scoring", "approved"]
    assert {s["source"] for s in processing["sources"]} == set(sources.SOURCES)
    assert all(s["payload"] for s in processing["sources"])
    assert all(c["round"] == 0 for c in processing["checks"])


def test_processing_journal_is_private():
    application = submit()
    response = client.get(f"/applications/{application['id']}/processing", headers=LOGISTICS)
    assert response.status_code == 404


def test_months_between():
    from datetime import date

    from app.conveyor.verification import months_between

    assert months_between(date(2025, 8, 20), date(2026, 10, 23)) == 14
    assert months_between(date(2025, 8, 25), date(2026, 10, 23)) == 13


GRAY = {
    "bki": {"bki_max_overdue_days_24m": 45, "bki_score": 450},
    "bank": {"neg_balance_days_share_12m": 0.4},
    "fns": {"court_cases_12m": 2},
}
HEAVY = {
    "bki": {"bki_max_overdue_days_24m": 90, "bki_score": 420},
    "bank": {"neg_balance_days_share_12m": 0.5},
    "fns": {"tax_arrears_flag": 1, "court_cases_12m": 3},
}


def test_scoring_is_monotonic():
    from app.scoring.inference import MODEL_VERSION, score

    base = {
        "business_age_months": 24, "revenue_12m": 14400000, "net_profit_12m": 3000000,
        "existing_monthly_payment": 0, "monthly_payment_rub": 50000, "existing_debt_total": 0,
        "bki_score": 640, "bki_max_overdue_days_24m": 0, "neg_balance_days_share_12m": 0.03,
        "court_cases_12m": 0, "tax_arrears_flag": 0, "mass_address_flag": 0,
        "amount_rub": 1500000, "collateral_value_rub": 0,
    }
    clean = score(base)
    worse = score({**base, "bki_max_overdue_days_24m": 40, "tax_arrears_flag": 1})
    secured = score({**base, "collateral_value_rub": 3000000})
    assert worse.pd > clean.pd > secured.pd
    assert {f.name for f in worse.factors if f.impact > 0} >= {"log_max_overdue", "tax_arrears_flag"}
    assert clean.model_version == MODEL_VERSION


def test_scoring_imputes_missing_sources():
    from app.scoring.inference import score

    result = score({
        "business_age_months": 24, "revenue_12m": 14400000, "net_profit_12m": 3000000,
        "existing_monthly_payment": 0, "monthly_payment_rub": 50000, "existing_debt_total": 0,
        "tax_arrears_flag": 0, "mass_address_flag": 0, "amount_rub": 1500000,
    })
    texts = [f.text for f in result.factors]
    assert 0 < result.pd < 1
    assert "нет скорингового балла БКИ" in texts


def test_risk_class_thresholds():
    from app.conveyor.decision import risk_class

    assert [risk_class(pd) for pd in (0.01, 0.03, 0.08, 0.2)] == ["A", "B", "C", "D"]


def test_approved_decision_has_terms_within_cash_flow():
    application = submit()
    decision = application["decision"]
    assert decision["outcome"] == "approved"
    assert decision["amount"] == FULL_DRAFT["amount"]
    assert decision["monthly_payment"] <= (FULL_DRAFT["declared_revenue"] - FULL_DRAFT["declared_expenses"]) / 1.25
    assert decision["reasons"][0].startswith("класс риска")


def test_amount_above_cash_flow_gives_counteroffer():
    application = submit(amount=8000000)
    decision = application["decision"]
    assert application["status"] == "counteroffer"
    assert decision["options"]
    assert decision["options"][0]["amount"] < 8000000
    assert all(o["amount"] < 8000000 or o["term_months"] > FULL_DRAFT["term_months"] for o in decision["options"])
    assert decision["options"][0]["changes"][0].startswith("сумма")


def test_gray_zone_without_assets_offers_msp_guarantee():
    OVERRIDES.update(GRAY)
    application = submit()
    assert application["status"] == "counteroffer"
    assert [o["security"] for o in application["decision"]["options"]] == ["msp_guarantee"]


def test_gray_zone_with_assets_offers_collateral():
    OVERRIDES.update(GRAY)
    OVERRIDES["bank"] = {**GRAY["bank"], "avg_monthly_account_turnover": 7900000}
    application = submit(headers=LOGISTICS, applicant_role="director", declared_revenue=8000000, declared_expenses=6500000)
    OVERRIDES.clear()
    securities = [o["security"] for o in application["decision"]["options"]]
    assert application["status"] == "counteroffer"
    assert securities[0] == "collateral"
    assert "msp_guarantee" in securities
    secured = application["decision"]["options"][0]
    processing = client.get(f"/applications/{application['id']}/processing", headers=LOGISTICS).json()
    assert secured["pd"] < processing["decisions"][0]["pd"]
    assert any(change.startswith("с залогом класс риска") for change in secured["changes"])


def test_high_risk_is_declined_with_factors():
    OVERRIDES.update(HEAVY)
    application = submit()
    assert application["status"] == "declined"
    assert "класс риска D" in application["decision"]["reasons"][0]
    assert len(application["decision"]["reasons"]) > 1


def test_accept_counteroffer():
    application = submit(amount=8000000)
    response = client.post(f"/applications/{application['id']}/accept", json={"option": 0}, headers=CAFE)
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["accepted_option"] == application["decision"]["options"][0]


def test_accept_collateral_option_sets_asset():
    OVERRIDES.update(GRAY)
    OVERRIDES["bank"] = {**GRAY["bank"], "avg_monthly_account_turnover": 7900000}
    application = submit(headers=LOGISTICS, applicant_role="director", declared_revenue=8000000, declared_expenses=6500000)
    response = client.post(f"/applications/{application['id']}/accept", json={"option": 0}, headers=LOGISTICS)
    assert response.json()["collateral_asset_id"] == application["decision"]["options"][0]["asset_id"]


def test_accept_unknown_option():
    application = submit(amount=8000000)
    response = client.post(f"/applications/{application['id']}/accept", json={"option": 9}, headers=CAFE)
    assert response.status_code == 422


def test_accept_without_counteroffer():
    application = submit()
    response = client.post(f"/applications/{application['id']}/accept", json={"option": 0}, headers=CAFE)
    assert response.status_code == 409


def test_decline_counteroffer_closes():
    application = submit(amount=8000000)
    response = client.post(f"/applications/{application['id']}/decline-offer", headers=CAFE)
    assert response.json()["status"] == "closed"


def test_ip_personal_loans_are_mentioned():
    OVERRIDES["bki"] = {"existing_monthly_payment": 30000, "personal_monthly_payment": 30000}
    application = submit()
    assert any("личные кредиты" in reason for reason in application["decision"]["reasons"])


def test_processing_journal_shows_scoring():
    application = submit()
    processing = client.get(f"/applications/{application['id']}/processing", headers=CAFE).json()
    decision = processing["decisions"][0]
    assert decision["risk_class"] in {"A", "B"}
    assert decision["model_version"] == MODEL_VERSION
    assert decision["factors"]


def test_risk_is_scored_on_offered_amount():
    application = submit(amount=8000000)
    decision = application["decision"]
    assert application["status"] == "counteroffer"
    assert all(o["security"] is None for o in decision["options"])
    assert "класс риска C" not in decision["reasons"][0]


def test_leasing_is_limited_by_cash_flow():
    application = submit(product_id="leasing", purpose="vehicle", amount=7000000, term_months=36)
    decision = application["decision"]
    limit = (FULL_DRAFT["declared_revenue"] - FULL_DRAFT["declared_expenses"]) / 1.25
    assert application["status"] == "counteroffer"
    assert decision["options"][0]["amount"] < 7000000
    assert decision["options"][0]["monthly_payment"] <= limit + 1
    assert any("лизингу" in reason for reason in decision["reasons"])


def test_affordable_leasing_is_approved_with_payment():
    application = submit(product_id="leasing", purpose="vehicle", amount=2000000, term_months=36)
    assert application["status"] == "approved"
    assert application["decision"]["monthly_payment"] > 0


def test_guarantee_is_scored_by_commission():
    application = submit(product_id="bank_guarantee", purpose="tender", amount=1500000, term_months=12)
    assert application["status"] == "approved"


def test_minor_factors_are_not_reasons():
    OVERRIDES.update(HEAVY)
    application = submit()
    processing = client.get(f"/applications/{application['id']}/processing", headers=CAFE).json()
    minor = {f["text"] for f in processing["decisions"][0]["factors"] if f["points"] < 0.25}
    assert application["status"] == "declined"
    assert minor
    assert not minor & set(application["decision"]["reasons"])


def test_guarantee_is_limited_by_reimbursement_capacity():
    application = submit(product_id="bank_guarantee", purpose="tender", amount=100000000, term_months=12)
    decision = application["decision"]
    assert application["status"] == "counteroffer"
    assert all(o["amount"] < 100000000 for o in decision["options"])
    assert any("предъявят к оплате" in reason for reason in decision["reasons"])


BANK = {"X-Role": "bank"}


def test_bank_api_requires_role():
    assert client.get("/bank/applications").status_code == 403
    assert client.get("/bank/applications", headers=CAFE).status_code == 403
    assert client.get("/bank/applications", headers={"X-Role": "client"}).status_code == 403


def test_bank_sees_applications_of_all_clients():
    cafe = submit()
    logistics = create(headers=LOGISTICS)
    applications = client.get("/bank/applications", headers=BANK).json()
    by_id = {a["id"]: a for a in applications}
    assert {cafe["id"], logistics["id"]} <= set(by_id)
    assert by_id[cafe["id"]]["client"]["id"] == "demo_cafe"
    assert by_id[cafe["id"]]["decision"]["outcome"] == "approved"
    assert by_id[logistics["id"]]["status"] == "draft"


def test_bank_filters_by_status_and_client():
    approved = submit()
    draft = create(headers=LOGISTICS)

    by_status = client.get("/bank/applications", params={"status": "approved"}, headers=BANK).json()
    assert [a["id"] for a in by_status] == [approved["id"]]

    by_client = client.get("/bank/applications", params={"client_id": "demo_logistics"}, headers=BANK).json()
    assert [a["id"] for a in by_client] == [draft["id"]]


def test_bank_rejects_unknown_status():
    response = client.get("/bank/applications", params={"status": "lost"}, headers=BANK)
    assert response.status_code == 422


def test_bank_journal_of_any_application():
    application = submit()
    journal = client.get(f"/bank/applications/{application['id']}", headers=BANK).json()
    assert journal["client"]["inn"]
    assert [h["to_status"] for h in journal["history"]][-1] == "approved"
    assert journal["sources"] and journal["checks"]
    assert journal["decisions"][0]["risk_class"] in {"A", "B"}


def test_bank_journal_unknown_application():
    assert client.get("/bank/applications/999999", headers=BANK).status_code == 404
