import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from .features import features

MODEL = json.loads((Path(__file__).parent / "model.json").read_text(encoding="utf-8"))
MODEL_VERSION = MODEL["version"]


@dataclass
class Factor:
    name: str
    value: float
    points: float
    impact: float
    text: str


@dataclass
class ScoreResult:
    pd: float
    model_version: str
    factors: list[Factor] = field(default_factory=list)


def sigmoid(z):
    return 1 / (1 + math.exp(-z))


def rub(x):
    return f"{x:,.0f}".replace(",", " ") + " ₽"


TEXTS = {
    "business_age_months": lambda v: f"срок бизнеса: {v['business_age_months']:.0f} мес.",
    "dscr": lambda v: f"денежный поток покрывает платежи по кредитам в {v['dscr']:.2f} раза",
    "bki_score": lambda v: f"скоринговый балл БКИ: {v['bki_score']:.0f}",
    "profit_margin": lambda v: f"рентабельность: {v['profit_margin']:.0%}",
    "collateral_coverage": lambda v: f"залог покрывает {v['collateral_coverage']:.0%} суммы",
    "log_revenue": lambda v: f"выручка за 12 мес.: {rub(v['revenue_12m'])}",
    "neg_balance_days_share_12m": lambda v: f"дней с отрицательным остатком на счёте: {v['neg_balance_days_share_12m']:.0%}",
    "log_max_overdue": lambda v: f"максимальная просрочка за 24 мес.: {math.expm1(v['log_max_overdue']):.0f} дн.",
    "debt_to_revenue": lambda v: f"текущий долг по кредитам: {v['debt_to_revenue']:.0%} годовой выручки",
    "amount_to_revenue": lambda v: f"сумма кредита: {v['amount_to_revenue']:.0%} годовой выручки",
    "court_cases_12m": lambda v: f"судебных дел за 12 мес.: {v['court_cases_12m']:.0f}",
    "tax_arrears_flag": lambda v: "есть налоговая задолженность" if v["tax_arrears_flag"] else "нет налоговой задолженности",
    "mass_address_flag": lambda v: "массовый адрес регистрации" if v["mass_address_flag"] else "адрес регистрации не массовый",
}

MISSING = {
    "bki_score": "нет скорингового балла БКИ",
    "neg_balance_days_share_12m": "нет данных об остатках на счёте",
}


def score(raw):
    values = features(raw)
    parts = []
    for feature in MODEL["features"]:
        name = feature["name"]
        imputed = values[name] is None
        value = feature["median"] if imputed else values[name]
        parts.append((name, value, imputed, feature["coef"] * (value - feature["mean"]) / feature["std"]))

    z = MODEL["intercept"] + sum(part for *_, part in parts)
    pd = sigmoid(z)
    shown = {**raw, **values}

    factors = []
    for name, value, imputed, part in parts:
        text = MISSING[name] if imputed else TEXTS[name](shown)
        factors.append(Factor(name, round(value, 4), round(part, 3), round(pd - sigmoid(z - part), 4), text))

    factors.sort(key=lambda f: -abs(f.impact))
    return ScoreResult(pd=round(pd, 4), model_version=MODEL_VERSION, factors=factors)
