import os

import httpx
import pytest

API_URL = os.getenv("SYSTEM_API_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("SYSTEM_FRONTEND_URL", "http://localhost:8501")
PGADMIN_URL = os.getenv("SYSTEM_PGADMIN_URL", "http://localhost:5050")
OLLAMA_URL = os.getenv("SYSTEM_OLLAMA_URL", "http://localhost:11434")


def load_spec():
    try:
        return httpx.get(f"{API_URL}/openapi.json", timeout=3).json()
    except (httpx.HTTPError, ValueError):
        return None


SPEC = load_spec()

pytestmark = pytest.mark.skipif(SPEC is None, reason=f"бэкенд не отвечает на {API_URL}")

VALID_REQUESTS = {
    ("GET", "/ranking/products"): None,
    ("POST", "/ranking/recommend"): {
        "client_id": "demo_cafe",
        "need": {"purpose": "cash_gap"},
    },
    ("POST", "/ranking/calculator/payment"): {
        "amount": 1000000,
        "annual_rate": 15,
        "term_months": 24,
    },
    ("POST", "/ranking/calculator/limit"): {
        "client_id": "demo_logistics",
        "annual_rate": 18,
        "term_months": 36,
    },
    ("POST", "/chat"): {
        "message": "Привет",
        "thread_id": "system-test",
        "client_id": "demo_cafe",
    },
    ("GET", "/clients"): None,
    ("GET", "/me"): None,
    ("GET", "/applications"): None,
    ("POST", "/applications"): {
        "product_id": "loan_any_purpose",
        "amount": 1000000,
        "term_months": 24,
        "purpose": "working_capital",
        "declared_revenue": 1200000,
        "declared_expenses": 950000,
        "bki_consent": True,
    },
    ("GET", "/applications/{application_id}"): None,
    ("PATCH", "/applications/{application_id}"): {"amount": 500000},
    ("POST", "/applications/{application_id}/submit"): None,
    ("POST", "/applications/{application_id}/withdraw"): None,
    ("POST", "/applications/{application_id}/process"): None,
    ("GET", "/applications/{application_id}/processing"): None,
    ("POST", "/applications/{application_id}/accept"): {"option": 0},
    ("POST", "/applications/{application_id}/decline-offer"): None,
    ("GET", "/bank/applications"): None,
    ("GET", "/bank/applications/{application_id}"): None,
}

CLIENT_HEADERS = {"X-Client-Id": "demo_cafe", "X-Role": "bank"}

EXPECTED_STATUS = {
    ("POST", "/applications"): 201,
    ("POST", "/applications/{application_id}/process"): 409,
    ("POST", "/applications/{application_id}/accept"): 409,
    ("POST", "/applications/{application_id}/decline-offer"): 409,
}

NEEDS_OLLAMA = {("POST", "/chat")}

INVALID_BODIES = [{}, {"unexpected": True}, []]


ROUTES = sorted(
    (method.upper(), path)
    for path, item in (SPEC or {}).get("paths", {}).items()
    for method in item
)
POST_ROUTES = [
    route for route in ROUTES
    if route[0] == "POST" and "requestBody" in SPEC["paths"][route[1]]["post"]
]


def ollama_up():
    try:
        return httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def new_application_id():
    response = httpx.post(
        f"{API_URL}/applications",
        json=VALID_REQUESTS[("POST", "/applications")],
        headers=CLIENT_HEADERS,
        timeout=10,
    )
    return response.json()["id"]


def url(path):
    if "{application_id}" in path:
        path = path.replace("{application_id}", str(new_application_id()))
    return f"{API_URL}{path}"


def call(method, path, body=None):
    return httpx.request(method, url(path), json=body, headers=CLIENT_HEADERS, timeout=60)


@pytest.mark.parametrize("url", [FRONTEND_URL, PGADMIN_URL])
def test_service_alive(url):
    assert httpx.get(url, timeout=10, follow_redirects=True).status_code == 200


def test_docs_alive():
    assert call("GET", "/docs").status_code == 200


def test_every_route_has_valid_request():
    missing = [route for route in ROUTES if route not in VALID_REQUESTS]
    assert not missing, f"добавьте пример запроса в VALID_REQUESTS: {missing}"


@pytest.mark.parametrize("route", ROUTES, ids=[f"{m} {p}" for m, p in ROUTES])
def test_valid_request(route):
    if route not in VALID_REQUESTS:
        pytest.skip("нет примера запроса")
    if route in NEEDS_OLLAMA and not ollama_up():
        pytest.skip("Ollama не запущена")
    response = call(*route, VALID_REQUESTS[route])
    assert response.status_code == EXPECTED_STATUS.get(route, 200), response.text


@pytest.mark.parametrize("body", INVALID_BODIES, ids=["empty", "unexpected", "list"])
@pytest.mark.parametrize("route", POST_ROUTES, ids=[p for _, p in POST_ROUTES])
def test_invalid_body_is_422(route, body):
    assert call(*route, body).status_code == 422


@pytest.mark.parametrize("route", POST_ROUTES, ids=[p for _, p in POST_ROUTES])
def test_not_json_is_422(route):
    response = httpx.post(
        url(route[1]),
        content="not json",
        headers={"Content-Type": "application/json", **CLIENT_HEADERS},
        timeout=10,
    )
    assert response.status_code == 422


def test_unknown_route_is_404():
    assert call("GET", "/no-such-route").status_code == 404


def test_recommend_contract():
    route = ("POST", "/ranking/recommend")
    data = call(*route, VALID_REQUESTS[route]).json()
    assert data["recommendations"]
    assert data["recommendations"][0]["product_id"] == "overdraft"
    for rec in data["recommendations"]:
        assert 0 <= rec["pd"] <= 1
        assert rec["risk_class"] in "ABCD"
        assert rec["reasons"]
    for rejected in data["rejected"]:
        assert rejected["reason"]


def submit_as(client_id, **fields):
    headers = {"X-Client-Id": client_id}
    created = httpx.post(
        f"{API_URL}/applications",
        json={**VALID_REQUESTS[("POST", "/applications")], "applicant_role": "director", **fields},
        headers=headers,
        timeout=10,
    ).json()
    return httpx.post(f"{API_URL}/applications/{created['id']}/submit", headers=headers, timeout=60).json()


def test_submit_queries_external_sources():
    application = submit_as("demo_cafe")
    statuses = {s["source"]: s["status"] for s in application["sources"]}
    assert application["status"] == "approved"
    assert statuses == {"egrul": "ok", "fns": "ok", "girbo": "not_found", "bank": "ok", "bki": "ok"}


def test_unavailable_source_does_not_break_application():
    application = submit_as("demo_unstable_bki")
    statuses = {s["source"]: s["status"] for s in application["sources"]}
    assert application["status"] == "checking"
    assert statuses["bki"] == "error"
    assert statuses["egrul"] == "ok"


@pytest.mark.parametrize("client_id", ["demo_liquidated", "demo_overdue", "demo_disqualified"])
def test_stop_factors_decline(client_id):
    application = submit_as(client_id)
    assert application["status"] == "declined"
    assert application["issues"]


def test_overstated_revenue_needs_info():
    application = submit_as("demo_cafe", declared_revenue=3000000)
    assert application["status"] == "needs_info"
    assert application["issues"]


def test_processing_journal_shows_external_answers():
    application = submit_as("demo_logistics")
    processing = httpx.get(
        f"{API_URL}/applications/{application['id']}/processing",
        headers={"X-Client-Id": "demo_logistics"},
        timeout=10,
    ).json()
    egrul = next(s for s in processing["sources"] if s["source"] == "egrul")
    assert egrul["payload"]["legal_form"] == "OOO"
    assert processing["checks"]


def test_gray_zone_ip_gets_msp_guarantee_offer():
    application = submit_as("demo_gray", declared_revenue=1100000, declared_expenses=800000)
    assert application["status"] == "counteroffer"
    assert application["decision"]["options"][0]["security"] == "msp_guarantee"


def test_gray_zone_ooo_gets_collateral_offer_and_accepts():
    application = submit_as("demo_gray_ooo", declared_revenue=2500000, declared_expenses=1900000)
    assert application["status"] == "counteroffer"
    assert application["decision"]["options"][0]["security"] == "collateral"

    accepted = httpx.post(
        f"{API_URL}/applications/{application['id']}/accept",
        json={"option": 0},
        headers={"X-Client-Id": "demo_gray_ooo"},
        timeout=10,
    ).json()
    assert accepted["status"] == "approved"
    assert accepted["collateral_asset_id"] is not None
