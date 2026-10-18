from langchain_core.tools import tool


@tool
def get_score(application_id: str) -> dict:
    """
    Получить предварительную оценку кредитного риска.

    Args:
        application_id: Идентификатор кредитной заявки.
    """
    return {
        "application_id": application_id,
        "risk_level": "low",
        "default_probability": 0.05,
        "status": "mock",
    }


@tool
def recommend_product(application_id: str) -> dict:
    """
    Подобрать кредитные продукты для предпринимателя.

    Args:
        application_id: Идентификатор кредитной заявки.
    """
    return {
        "application_id": application_id,
        "products": [
            {
                "product_id": "credit_001",
                "name": "Оборотный кредит",
                "score": 0.92,
                "explanation": "Подходит для пополнения оборотных средств.",
            },
            {
                "product_id": "credit_002",
                "name": "Кредитная линия",
                "score": 0.85,
                "explanation": "Подходит для регулярного финансирования.",
            },
        ],
        "status": "mock",
    }