from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Client(Base):
    __tablename__ = "conveyor_clients"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    inn: Mapped[str] = mapped_column(String(12), unique=True)
    legal_form: Mapped[str] = mapped_column(String(8))
    name: Mapped[str]
    okved: Mapped[str]
    tax_regime: Mapped[str]
    has_alfa_account: Mapped[bool]
    owner_name: Mapped[str]
    owner_age: Mapped[int | None]

    assets: Mapped[list["Asset"]] = relationship(back_populates="client", order_by="Asset.id")


class Asset(Base):
    __tablename__ = "conveyor_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("conveyor_clients.id"))
    kind: Mapped[str] = mapped_column(String(16))
    description: Mapped[str]
    market_value: Mapped[float]

    client: Mapped[Client] = relationship(back_populates="assets")


class Application(Base):
    __tablename__ = "conveyor_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("conveyor_clients.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")

    product_id: Mapped[str | None]
    amount: Mapped[float | None]
    term_months: Mapped[int | None]
    purpose: Mapped[str | None]
    declared_revenue: Mapped[float | None]
    declared_expenses: Mapped[float | None]
    declared_debt_payment: Mapped[float | None]
    applicant_role: Mapped[str | None]
    collateral_asset_id: Mapped[int | None] = mapped_column(ForeignKey("conveyor_assets.id"))
    bki_consent: Mapped[bool] = mapped_column(default=False)
    info_rounds: Mapped[int] = mapped_column(default=0)
    accepted_option: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    history: Mapped[list["StatusChange"]] = relationship(order_by="StatusChange.id")
    sources: Mapped[list["SourceResponse"]] = relationship(order_by="SourceResponse.id")
    checks: Mapped[list["Check"]] = relationship(order_by="Check.id")
    decisions: Mapped[list["Decision"]] = relationship(order_by="Decision.id")

    @property
    def decision(self):
        return self.decisions[-1] if self.decisions else None

    @property
    def issues(self):
        if not self.checks:
            return []
        last_round = self.checks[-1].round
        return [
            check.message for check in self.checks
            if check.round == last_round and check.kind in ("stop_factor", "discrepancy")
        ]


class StatusChange(Base):
    __tablename__ = "conveyor_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("conveyor_applications.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourceResponse(Base):
    __tablename__ = "conveyor_source_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("conveyor_applications.id"), index=True)
    source: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict | None] = mapped_column(JSON)
    duration_ms: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Check(Base):
    __tablename__ = "conveyor_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("conveyor_applications.id"), index=True)
    round: Mapped[int]
    kind: Mapped[str] = mapped_column(String(16))
    code: Mapped[str] = mapped_column(String(32))
    message: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Decision(Base):
    __tablename__ = "conveyor_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("conveyor_applications.id"), index=True)
    outcome: Mapped[str] = mapped_column(String(32))
    pd: Mapped[float | None]
    risk_class: Mapped[str | None] = mapped_column(String(4))
    amount: Mapped[float | None]
    term_months: Mapped[int | None]
    rate: Mapped[float | None]
    monthly_payment: Mapped[float | None]
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    factors: Mapped[list] = mapped_column(JSON, default=list)
    options: Mapped[list] = mapped_column(JSON, default=list)
    model_version: Mapped[str | None]
    policy_version: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
