from app.policy import POLICY
from app.ranking.catalog import get_product

from . import decision, sources, verification
from .models import Application, Asset, Check, Decision, SourceResponse, StatusChange

TRANSITIONS = {
    ("draft", "submitted"): "client",
    ("draft", "withdrawn"): "client",
    ("submitted", "checking"): "system",
    ("submitted", "withdrawn"): "client",
    ("checking", "needs_info"): "system",
    ("checking", "declined"): "system",
    ("checking", "scoring"): "system",
    ("needs_info", "submitted"): "client",
    ("needs_info", "declined"): "system",
    ("needs_info", "withdrawn"): "client",
    ("scoring", "approved"): "system",
    ("scoring", "counteroffer"): "system",
    ("scoring", "declined"): "system",
    ("counteroffer", "approved"): "client",
    ("counteroffer", "closed"): "client",
}

EDITABLE = {"draft", "needs_info"}
MAX_INFO_ROUNDS = POLICY.verification.max_info_rounds

REQUIRED_FOR_SUBMIT = {
    "product_id": "продукт",
    "amount": "сумма",
    "term_months": "срок",
    "purpose": "цель",
    "declared_revenue": "выручка в месяц",
    "declared_expenses": "расходы в месяц",
}


class ConveyorError(Exception):
    status_code = 400

    def __init__(self, message, **details):
        super().__init__(message)
        self.message = message
        self.details = details


class NotAllowed(ConveyorError):
    status_code = 409


class Invalid(ConveyorError):
    status_code = 422


def transition(session, application, to_status, actor, reason=None):
    expected_actor = TRANSITIONS.get((application.status, to_status))

    if expected_actor is None:
        raise NotAllowed(f"переход {application.status} → {to_status} недопустим")
    if expected_actor != actor:
        raise NotAllowed(f"переход {application.status} → {to_status} выполняет {expected_actor}, а не {actor}")

    application.history.append(StatusChange(
        from_status=application.status,
        to_status=to_status,
        actor=actor,
        reason=reason,
    ))
    application.status = to_status


def lock(session, application):
    session.refresh(application, with_for_update=True)


def validate_fields(session, client, fields):
    product_id = fields.get("product_id")
    if product_id is not None:
        try:
            get_product(product_id)
        except KeyError:
            raise Invalid(f"продукт {product_id} не найден")

    asset_id = fields.get("collateral_asset_id")
    if asset_id is not None:
        asset = session.get(Asset, asset_id)
        if asset is None or asset.client_id != client.id:
            raise Invalid(f"актив {asset_id} не найден у клиента")


def create(session, client, fields):
    validate_fields(session, client, fields)

    application = Application(
        client_id=client.id,
        status="draft",
        history=[StatusChange(from_status=None, to_status="draft", actor="client", reason="черновик создан")],
        **fields,
    )
    session.add(application)
    session.commit()
    return application


def update(session, client, application, fields):
    lock(session, application)

    if application.status not in EDITABLE:
        session.rollback()
        raise NotAllowed(f"заявку в статусе {application.status} нельзя изменить")

    validate_fields(session, client, fields)

    for name, value in fields.items():
        setattr(application, name, value)

    session.commit()
    return application


def missing_fields(client, application):
    missing = [title for name, title in REQUIRED_FOR_SUBMIT.items() if getattr(application, name) is None]

    if client.legal_form == "ooo" and application.applicant_role is None:
        missing.append("роль заявителя")
    if not application.bki_consent:
        missing.append("согласие на запрос в БКИ")

    return missing


def submit(session, client, application):
    lock(session, application)

    if application.status not in EDITABLE:
        session.rollback()
        raise NotAllowed(f"заявку в статусе {application.status} нельзя подать")

    missing = missing_fields(client, application)
    if missing:
        session.rollback()
        raise Invalid("заявка заполнена не полностью", missing=missing)

    transition(session, application, "submitted", "client", "заявка подана")
    session.commit()
    return application


def pending_sources(application):
    done = {r.source for r in application.sources if r.status not in sources.FAILED}
    return [source for source in sources.SOURCES if source not in done]


def run_checks(session, client, application):
    lock(session, application)

    if application.status == "submitted":
        transition(session, application, "checking", "system", "проверка запущена")

    if application.status != "checking":
        session.rollback()
        raise NotAllowed(f"заявка в статусе {application.status} не проверяется")

    for result in sources.fetch_all(client.inn, pending_sources(application), application.id):
        application.sources.append(SourceResponse(**result))

    answers = latest_answers(application)
    if all(source in answers for source in verification.REQUIRED_SOURCES):
        evaluate(session, client, application, answers)

    if application.status == "scoring":
        apply_decision(session, client, application, answers)

    session.commit()
    return application


def apply_decision(session, client, application, answers):
    result = decision.decide(client, application, answers)

    application.decisions.append(Decision(
        outcome=result.outcome,
        pd=result.pd,
        risk_class=result.risk_class,
        amount=result.amount,
        term_months=result.term_months,
        rate=result.rate,
        monthly_payment=result.monthly_payment,
        reasons=result.reasons,
        factors=result.factors,
        options=result.options,
        model_version=result.model_version,
    ))
    transition(session, application, result.outcome, "system", "; ".join(result.reasons[:2]))


def accept_offer(session, application, option_index):
    lock(session, application)

    if application.status != "counteroffer":
        session.rollback()
        raise NotAllowed(f"в статусе {application.status} нет предложения для выбора")

    options = application.decision.options
    if not 0 <= option_index < len(options):
        session.rollback()
        raise Invalid(f"варианта {option_index} нет, доступно: {len(options)}")

    chosen = options[option_index]
    application.accepted_option = chosen
    if chosen.get("asset_id") is not None:
        application.collateral_asset_id = chosen["asset_id"]

    transition(session, application, "approved", "client", "клиент принял вариант " + str(option_index + 1))
    session.commit()
    return application


def decline_offer(session, application):
    lock(session, application)

    try:
        transition(session, application, "closed", "client", "клиент отказался от предложения")
    except NotAllowed:
        session.rollback()
        raise

    session.commit()
    return application


def latest_answers(application):
    answers = {}
    for response in application.sources:
        if response.status not in sources.FAILED:
            answers[response.source] = (response.status, response.payload)
    return answers


def evaluate(session, client, application, answers):
    findings = verification.verify(client, application, answers)

    for finding in findings:
        application.checks.append(Check(
            round=application.info_rounds,
            kind=finding.kind,
            code=finding.code,
            message=finding.message,
            data=finding.data,
        ))

    stops = [f.message for f in findings if f.kind == "stop_factor"]
    discrepancies = [f.message for f in findings if f.kind == "discrepancy"]

    if stops:
        transition(session, application, "declined", "system", "; ".join(stops))
    elif discrepancies and application.info_rounds >= MAX_INFO_ROUNDS:
        transition(
            session, application, "declined", "system",
            "не удалось подтвердить данные: " + "; ".join(discrepancies),
        )
    elif discrepancies:
        application.info_rounds += 1
        transition(session, application, "needs_info", "system", "; ".join(discrepancies))
    else:
        transition(session, application, "scoring", "system", "проверки пройдены")


def withdraw(session, application):
    lock(session, application)

    try:
        transition(session, application, "withdrawn", "client", "заявка отозвана клиентом")
    except NotAllowed:
        session.rollback()
        raise

    session.commit()
    return application
