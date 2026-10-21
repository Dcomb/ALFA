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
    },
}

NEEDS_OLLAMA = {("POST", "/chat")}

INVALID_BODIES = [{}, {"unexpected": True}, []]


ROUTES = sorted(
    (method.upper(), path)
    for path, item in (SPEC or {}).get("paths", {}).items()
    for method in item
)
POST_ROUTES = [route for route in ROUTES if route[0] == "POST"]


def ollama_up():
    try:
        return httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def call(method, path, body=None):
    return httpx.request(method, f"{API_URL}{path}", json=body, timeout=60)


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
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("body", INVALID_BODIES, ids=["empty", "unexpected", "list"])
@pytest.mark.parametrize("route", POST_ROUTES, ids=[p for _, p in POST_ROUTES])
def test_invalid_body_is_422(route, body):
    assert call(*route, body).status_code == 422


@pytest.mark.parametrize("route", POST_ROUTES, ids=[p for _, p in POST_ROUTES])
def test_not_json_is_422(route):
    response = httpx.post(
        f"{API_URL}{route[1]}",
        content="not json",
        headers={"Content-Type": "application/json"},
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
        assert 0 <= rec["approval_prob"] <= 1
        assert rec["reasons"]
    for rejected in data["rejected"]:
        assert rejected["reason"]
