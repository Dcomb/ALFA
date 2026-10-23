from dataclasses import dataclass, field
from datetime import date

from app.policy import POLICY
from app.ranking import calculator as calc
from app.ranking.catalog import get_product
from app.ranking.engine import LOAN_TYPES, build_offer, eligibility_problems, rub
from app.ranking.schemas import ClientProfile, Need

from . import scoring
from .verification import months_between

ASSET_NAMES = {"real_estate": "недвижимость", "vehicle": "транспорт", "equipment": "оборудование"}


@dataclass
class DecisionResult:
    outcome: str
    pd: float | None = None
    risk_class: str | None = None
    model_version: str | None = None
    amount: float | None = None
    term_months: int | None = None
    rate: float | None = None
    monthly_payment: float | None = None
    reasons: list[str] = field(default_factory=list)
    factors: list[dict] = field(default_factory=list)
    options: list[dict] = field(default_factory=list)


def risk_class(pd):
    bounds = POLICY.risk_classes
    if pd < bounds.A:
        return "A"
    if pd < bounds.B:
        return "B"
    if pd < bounds.C:
        return "C"
    return "D"


def verified_finances(application, answers):
    turnover = answers["bank"][1]["avg_monthly_account_turnover"]
    revenue = min(application.declared_revenue, turnover)
    share = revenue / application.declared_revenue if application.declared_revenue else 1.0
    return revenue, application.declared_expenses * share


def verified_profile(client, application, answers, today):
    bki = answers["bki"][1] or {}
    egrul = answers["egrul"][1]
    revenue, expenses = verified_finances(application, answers)

    return ClientProfile(
        client_id=client.id,
        legal_form=client.legal_form,
        business_age_months=months_between(date.fromisoformat(egrul["registration_date"]), today),
        owner_age=client.owner_age,
        monthly_revenue=revenue,
        monthly_expenses=expenses,
        existing_monthly_debt=bki.get("existing_monthly_payment", 0),
        in_msp_registry=True,
        has_alfa_account=client.has_alfa_account,
        delinquency_180d=bki.get("current_overdue_days", 0) > 0,
    )


def option(product, rate, term, amount, requested, requested_term, changes=None, security=None, asset_id=None):
    payment = None
    if product["type"] in LOAN_TYPES and product["id"] != "overdraft":
        payment = calc.annuity_payment(amount, rate, term)

    texts = list(changes or [])
    if amount < requested - 1:
        texts.insert(0, f"сумма {rub(amount)} вместо {rub(requested)}")
    if term != requested_term:
        texts.append(f"срок {term} мес. вместо {requested_term}")

    return {
        "amount": round(amount, 2),
        "term_months": term,
        "rate": rate,
        "monthly_payment": round(payment, 2) if payment is not None else None,
        "security": security,
        "asset_id": asset_id,
        "changes": texts,
    }


def secured_options(client, application, product, offer, rate):
    term = offer["term_months"]
    limit = application.amount if offer["max_amount"] is None else min(application.amount, offer["max_amount"])
    assets = [a for a in client.assets if application.collateral_asset_id in (None, a.id)]

    options = []
    for asset in sorted(assets, key=lambda a: -a.market_value):
        amount = min(limit, asset.market_value * calc.COLLATERAL_LTV)
        label = f"залог: {ASSET_NAMES.get(asset.kind, asset.kind)} — {asset.description}, оценка {rub(asset.market_value)}"
        options.append(option(product, rate, term, amount, application.amount, application.term_months,
                              [label], "collateral", asset.id))

    options.append(option(
        product, rate, term, limit, application.amount, application.term_months,
        ["поручительство Корпорации МСП (покрывает до 50% кредита, для вас бесплатно)"], "msp_guarantee",
    ))
    return options[:POLICY.concessions.max_variants]


def unsecured_options(application, product, offer, rate):
    options = [option(product, rate, offer["term_months"], offer["amount"], application.amount, application.term_months)]
    for alternative in offer["alternatives"]:
        options.append(option(product, rate, alternative.term_months, alternative.amount,
                              application.amount, application.term_months))
    return options[:POLICY.concessions.max_variants]


def personal_debt_reason(client, answers):
    personal = (answers["bki"][1] or {}).get("personal_monthly_payment", 0)
    if client.legal_form == "ip" and personal > 0:
        return f"учтены ваши личные кредиты: {rub(personal)} в месяц"
    return None


def decide(client, application, answers, today=None):
    today = today or date.today()
    product = get_product(application.product_id)
    need = Need(purpose=application.purpose, amount=application.amount, term_months=application.term_months)
    profile = verified_profile(client, application, answers, today)
    notes = [note for note in [personal_debt_reason(client, answers)] if note]

    problems = [p for p in eligibility_problems(profile, product, need) if p[2][0] != "collateral"]
    if problems:
        return DecisionResult(
            outcome="declined",
            reasons=[p[0] for p in problems] + [p[1] for p in problems if p[1]] + notes,
        )

    if product.get("requires_own_collateral") and not client.assets:
        return DecisionResult(outcome="declined", reasons=["для продукта нужен залог, а активов для залога нет"] + notes)

    if product.get("requires_own_collateral"):
        largest = max(client.assets, key=lambda a: a.market_value)
        profile = profile.model_copy(update={"has_collateral": True, "collateral_value": largest.market_value})

    built, problem = build_offer(profile, product, need)
    if problem:
        return DecisionResult(outcome="declined", reasons=[problem[0]] + ([problem[1]] if problem[1] else []) + notes)

    offer, _ = built
    rate = offer["rate"] if offer["rate"] is not None else product.get("rate_from")
    features = scoring.features_from(
        answers, profile.business_age_months, profile.monthly_revenue, profile.monthly_expenses,
        application.amount, rate or 0, offer["term_months"],
    )
    result = scoring.score(features)
    cls = risk_class(result.pd)
    factors = [vars(f) for f in result.factors]
    adverse = [f.text for f in result.factors if f.impact > 0][:3]
    summary = f"класс риска {cls}: вероятность дефолта {result.pd:.1%}"
    base = dict(pd=result.pd, risk_class=cls, model_version=result.model_version, factors=factors)

    if cls == "D":
        return DecisionResult(outcome="declined", reasons=[summary] + adverse + notes, **base)

    if cls == "C":
        return DecisionResult(
            outcome="counteroffer",
            reasons=[summary, "при таком риске нужен залог или поручительство"] + adverse + notes,
            options=secured_options(client, application, product, offer, rate),
            **base,
        )

    if offer["amount"] is not None and offer["amount"] < application.amount - 1:
        return DecisionResult(
            outcome="counteroffer",
            reasons=[summary, f"по денежному потоку доступно до {rub(offer['max_amount'])}"] + notes,
            options=unsecured_options(application, product, offer, rate),
            **base,
        )

    approved = option(product, rate, offer["term_months"], application.amount, application.amount, application.term_months)
    reasons = [summary] + offer["warnings"]
    if approved["monthly_payment"] is not None:
        reasons.append(f"платёж {rub(approved['monthly_payment'])} в месяц укладывается в денежный поток")
    return DecisionResult(
        outcome="approved",
        amount=approved["amount"],
        term_months=approved["term_months"],
        rate=rate,
        monthly_payment=approved["monthly_payment"],
        reasons=reasons + notes,
        **base,
    )
