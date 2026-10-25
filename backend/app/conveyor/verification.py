from dataclasses import dataclass, field
from datetime import date

from app.policy import POLICY
from app.ranking.engine import rub

REQUIRED_SOURCES = ("egrul", "fns", "bank", "bki")
REVENUE_TOLERANCE = POLICY.verification.revenue_tolerance
DEBT_TOLERANCE = POLICY.verification.debt_tolerance
MAX_CURRENT_OVERDUE_DAYS = POLICY.verification.max_current_overdue_days
INACTIVE_STATUSES = {"liquidating": "в процессе ликвидации", "liquidated": "ликвидирована"}


@dataclass
class Finding:
    kind: str
    code: str
    message: str
    data: dict = field(default_factory=dict)


def months_between(start, end):
    return (end.year - start.year) * 12 + end.month - start.month - (end.day < start.day)


def check_registry(answers, today):
    status, egrul = answers["egrul"]

    if status == "not_found":
        return [Finding("stop_factor", "not_in_registry", "компания не найдена в госреестре")]

    findings = []
    registry_status = egrul.get("registry_status")

    if registry_status in INACTIVE_STATUSES:
        findings.append(Finding(
            "stop_factor",
            "inactive_company",
            f"по данным госреестра компания {INACTIVE_STATUSES[registry_status]}",
            {"registry_status": registry_status},
        ))

    registered = date.fromisoformat(egrul["registration_date"])
    age = months_between(registered, today)
    findings.append(Finding(
        "info",
        "business_age",
        f"по госреестру бизнес зарегистрирован {registered:%d.%m.%Y}, {age} мес.",
        {"registration_date": egrul["registration_date"], "business_age_months": age},
    ))
    return findings


def check_fns(client, answers):
    status, fns = answers["fns"]

    if status != "ok":
        return [Finding("info", "fns_no_data", "ФНС: сведений о рисках нет")]

    if client.legal_form == "ooo" and fns.get("disqualified_person_flag"):
        return [Finding(
            "stop_factor",
            "disqualified_director",
            "руководитель дисквалифицирован (ст. 3.11 КоАП) и не вправе руководить организацией",
        )]

    flags = {name: fns.get(name, 0) for name in ("tax_arrears_flag", "mass_address_flag", "court_cases_12m")}
    return [Finding("info", "fns_flags", "ФНС: признаки риска учтены в скоринге", flags)]


def check_bki(application, answers):
    status, bki = answers["bki"]

    if status == "not_found":
        return [Finding("info", "no_credit_history", "кредитной истории нет", {"existing_monthly_payment": 0})]

    findings = []
    overdue = bki.get("current_overdue_days", 0)

    if overdue > MAX_CURRENT_OVERDUE_DAYS:
        findings.append(Finding(
            "stop_factor",
            "current_overdue",
            f"текущая просрочка по кредитам {overdue} дн.",
            {"current_overdue_days": overdue},
        ))

    payment = bki.get("existing_monthly_payment", 0)
    declared = application.declared_debt_payment

    if declared is not None and payment > 0 and declared < payment * (1 - DEBT_TOLERANCE):
        findings.append(Finding(
            "discrepancy",
            "hidden_debt",
            f"по данным БКИ платежи по кредитам {rub(payment)} в месяц, вы указали {rub(declared)} — уточните",
            {"bki_monthly_payment": payment, "declared_debt_payment": declared},
        ))
    else:
        findings.append(Finding(
            "info",
            "debt_from_bki",
            f"платежи по действующим кредитам по данным БКИ: {rub(payment)} в месяц",
            {"existing_monthly_payment": payment},
        ))

    return findings


def check_revenue(application, answers):
    status, bank = answers["bank"]

    if status != "ok":
        return [Finding(
            "discrepancy",
            "revenue_unconfirmed",
            "нет данных об оборотах по счёту, выручку подтвердить нечем",
        )]

    turnover = bank["avg_monthly_account_turnover"]
    declared = application.declared_revenue

    if turnover < declared * (1 - REVENUE_TOLERANCE):
        return [Finding(
            "discrepancy",
            "revenue_above_turnover",
            f"обороты по счёту {rub(turnover)} в месяц, заявленная выручка {rub(declared)} — уточните выручку",
            {"turnover": turnover, "declared_revenue": declared},
        )]

    return [Finding(
        "info",
        "revenue_confirmed",
        f"выручка подтверждена оборотами по счёту: {rub(turnover)} в месяц",
        {"turnover": turnover, "declared_revenue": declared},
    )]


def verify(client, application, answers, today=None):
    today = today or date.today()

    findings = check_registry(answers, today)
    if any(f.kind == "stop_factor" for f in findings):
        return findings

    findings += check_fns(client, answers)
    findings += check_bki(application, answers)
    findings += check_revenue(application, answers)
    return findings
