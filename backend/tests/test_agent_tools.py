from app.agent.output import sanitize_answer_links
from app.agent.tools import TOOLS, normalize_product_id, normalize_purpose
from app.ranking.clients import DEMO_CLIENTS


def test_normalize_russian_purpose():
    assert normalize_purpose("Для покупки оборудования") == "investment"
    assert normalize_purpose("закрыть кассовый разрыв") == "cash_gap"
    assert normalize_purpose("на пополнение оборотных средств") == "working_capital"


def test_normalize_product_name():
    assert (
        normalize_product_id("Кредит на любые бизнес-цели (без залога)")
        == "loan_any_purpose"
    )


def test_untrusted_links_are_removed():
    answer = (
        "[Альфа](https://alfabank.ru/sme) "
        "[выдуманный источник](https://example.com/product) "
        "[другой банк](https://www.sberbank.ru/credit)"
    )

    cleaned = sanitize_answer_links(answer)

    assert "https://alfabank.ru/sme" in cleaned
    assert "example.com" not in cleaned
    assert "sberbank.ru" not in cleaned
    assert "выдуманный источник" in cleaned


def test_agent_has_risk_and_document_tools():
    names = {tool.name for tool in TOOLS}
    assert "assess_application_risk" in names
    assert "assess_company_risk" in names
    assert "inspect_application_documents" in names


def test_all_demo_clients_have_recommendation_profiles():
    assert {
        "demo_cafe", "demo_logistics", "demo_newbie", "demo_unstable_bki",
        "demo_liquidated", "demo_overdue", "demo_disqualified", "demo_gray",
        "demo_gray_ooo",
    } <= set(DEMO_CLIENTS)
