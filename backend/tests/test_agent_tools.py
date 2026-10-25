from app.agent.output import sanitize_answer_links
from app.agent.tools import normalize_product_id, normalize_purpose


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
