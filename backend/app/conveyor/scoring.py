import math
from dataclasses import dataclass, field

from app.ranking.calculator import annuity_payment

MODEL_VERSION = "expert-scorecard"
INTERCEPT = -3.4


@dataclass
class Factor:
    name: str
    value: float
    impact: float
    text: str


@dataclass
class ScoreResult:
    pd: float
    model_version: str
    factors: list[Factor] = field(default_factory=list)


def sigmoid(z):
    return 1 / (1 + math.exp(-z))


def debt_load(features):
    flow = features["monthly_revenue"] - features["monthly_expenses"]
    payments = features["existing_monthly_payment"] + features["new_monthly_payment"]
    return payments / flow if flow > 0 else 10.0


def contributions(features):
    load = debt_load(features)
    return [
        ("max_overdue_days_24m", features["max_overdue_days_24m"],
         0.02 * min(features["max_overdue_days_24m"], 90),
         "максимальная просрочка за 24 мес.: {value:.0f} дн."),
        ("overdue_90_24m", features["overdue_90_24m"],
         0.8 * min(features["overdue_90_24m"], 3),
         "просрочки 90+ дней за 24 мес.: {value:.0f}"),
        ("inquiries_6m", features["inquiries_6m"],
         0.12 * min(features["inquiries_6m"], 10),
         "запросов в другие банки за 6 мес.: {value:.0f}"),
        ("business_age_months", features["business_age_months"],
         -0.015 * min(features["business_age_months"], 60),
         "срок бизнеса: {value:.0f} мес."),
        ("debt_load", load,
         1.5 * max(load - 0.5, 0),
         "долговая нагрузка с новым кредитом: {value:.0%} операционного потока"),
        ("tax_arrears", features["tax_arrears"],
         0.6 * features["tax_arrears"],
         "налоговая задолженность"),
        ("mass_address", features["mass_address"],
         0.4 * features["mass_address"],
         "массовый адрес регистрации"),
        ("court_cases_12m", features["court_cases_12m"],
         0.1 * min(features["court_cases_12m"], 5),
         "судебных дел за 12 мес.: {value:.0f}"),
        ("bki_score", features["bki_score"],
         -0.004 * (features["bki_score"] - 600),
         "скоринговый балл БКИ: {value:.0f}"),
    ]


def score(features):
    parts = contributions(features)
    z = INTERCEPT + sum(part for _, _, part, _ in parts)
    pd = sigmoid(z)

    factors = []
    for name, value, part, template in parts:
        if part == 0:
            continue
        impact = pd - sigmoid(z - part)
        factors.append(Factor(name, value, round(impact, 4), template.format(value=value)))

    factors.sort(key=lambda f: -abs(f.impact))
    return ScoreResult(pd=round(pd, 4), model_version=MODEL_VERSION, factors=factors)


def features_from(answers, business_age_months, monthly_revenue, monthly_expenses, amount, rate, term_months):
    bki = answers["bki"][1] or {}
    fns = answers["fns"][1] or {}
    return {
        "max_overdue_days_24m": bki.get("bki_max_overdue_days_24m", 0),
        "overdue_90_24m": bki.get("bki_overdue_90_24m", 0),
        "inquiries_6m": bki.get("bki_inquiries_6m", 0),
        "bki_score": bki.get("bki_score", 600),
        "existing_monthly_payment": bki.get("existing_monthly_payment", 0),
        "new_monthly_payment": annuity_payment(amount, rate, term_months),
        "business_age_months": business_age_months,
        "monthly_revenue": monthly_revenue,
        "monthly_expenses": monthly_expenses,
        "tax_arrears": fns.get("tax_arrears_flag", 0),
        "mass_address": fns.get("mass_address_flag", 0),
        "court_cases_12m": fns.get("court_cases_12m", 0),
    }
