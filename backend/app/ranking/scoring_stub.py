import math

from .calculator import annuity_payment
from .schemas import ScoreResponse

RISK_PREMIUM = 6.0


def _sigmoid(z):
    return 1 / (1 + math.exp(-z))


def get_score(client, product, amount, term_months):
    rate_from = product.get('rate_from')
    operating = client.monthly_revenue - client.monthly_expenses
    payment = annuity_payment(amount, rate_from or 15.0, term_months) if product['type'] in ('term_loan', 'line', 'revolving') else 0.0
    load = (client.existing_monthly_debt + payment) / operating if operating > 0 else 10.0

    z = (
        0.5
        + 0.03 * min(client.business_age_months, 60)
        - 2.5 * max(load - 0.5, 0)
        - 2.0 * client.delinquency_180d
        + 0.5 * client.has_alfa_account
    )
    p = _sigmoid(z)
    rate = round(rate_from + RISK_PREMIUM * (1 - p), 2) if rate_from is not None else None
    return ScoreResponse(product_id=product['id'], approval_prob=round(p, 4), rate=rate, stub=True)
