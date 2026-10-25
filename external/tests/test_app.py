from fastapi.testclient import TestClient

import app as external

client = TestClient(external.app)

CAFE = "000010100195"
LOGISTICS = "0000201003"
UNSTABLE = "000040100499"


def test_known_inn():
    egrul = client.get(f"/egrul/{CAFE}").json()
    assert egrul["legal_form"] == "IP"
    assert egrul["registry_status"] == "active"


def test_unknown_inn_is_404():
    assert client.get("/egrul/123").status_code == 404


def test_ip_has_no_accounting_reports():
    assert client.get(f"/girbo/{CAFE}").status_code == 404
    assert client.get(f"/girbo/{LOGISTICS}").json()["total_assets"] > 0


def test_configured_failure():
    assert client.get(f"/bki/{UNSTABLE}").status_code == 503
    assert client.get(f"/egrul/{UNSTABLE}").status_code == 200


def test_every_company_has_core_sources():
    for inn, company in external.WORLD.items():
        for source in ("egrul", "fns", "bank", "bki"):
            assert source in company, (inn, source)
