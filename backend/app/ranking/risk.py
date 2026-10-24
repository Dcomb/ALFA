from app.policy import POLICY
from app.scoring.inference import score

from . import calculator as calc


def scoring_input(client, amount, payment, collateral_value):
    return {
        'business_age_months': client.business_age_months,
        'revenue_12m': client.monthly_revenue * 12,
        'net_profit_12m': (client.monthly_revenue - client.monthly_expenses) * 12,
        'existing_monthly_payment': client.existing_monthly_debt,
        'monthly_payment_rub': payment,
        'amount_rub': amount,
        'collateral_value_rub': collateral_value,
    }


def estimate(client, product, amount, term_months):
    payment = calc.monthly_cost(product, amount, product.get('rate_from'), term_months)
    collateral = client.collateral_value if client.has_collateral else 0
    raw = scoring_input(client, amount, payment, collateral)
    if client.delinquency_180d:
        raw['bki_max_overdue_days_24m'] = POLICY.verification.max_current_overdue_days
    return score(raw)
