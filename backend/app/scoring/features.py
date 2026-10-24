import math


def clip(x, low, high):
    return min(max(x, low), high)


def known(x):
    return None if x is None or x != x else x


def features(raw):
    revenue = max(raw["revenue_12m"], 1)
    payments = max(raw["existing_monthly_payment"] + raw["monthly_payment_rub"], 1)
    return {
        "business_age_months": raw["business_age_months"],
        "dscr": clip(raw["net_profit_12m"] / 12 / payments, -2, 10),
        "bki_score": known(raw.get("bki_score")),
        "profit_margin": clip(raw["net_profit_12m"] / revenue, -2, 1),
        "collateral_coverage": clip((known(raw.get("collateral_value_rub")) or 0) / raw["amount_rub"], 0, 3),
        "log_revenue": math.log1p(max(raw["revenue_12m"], 0)),
        "neg_balance_days_share_12m": known(raw.get("neg_balance_days_share_12m")),
        "log_max_overdue": math.log1p(known(raw.get("bki_max_overdue_days_24m")) or 0),
        "debt_to_revenue": clip(raw["existing_debt_total"] / revenue, 0, 5),
        "amount_to_revenue": clip(raw["amount_rub"] / revenue, 0, 5),
        "court_cases_12m": known(raw.get("court_cases_12m")) or 0,
        "tax_arrears_flag": raw["tax_arrears_flag"],
        "mass_address_flag": raw["mass_address_flag"],
    }
