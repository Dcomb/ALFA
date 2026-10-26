from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ranking.schemas import NeedTag

ApplicantRole = Literal["owner", "director", "accountant", "representative"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ApplicationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str | None = None
    amount: float | None = Field(default=None, gt=0)
    term_months: int | None = Field(default=None, gt=0, le=360)
    purpose: NeedTag | None = None
    declared_revenue: float | None = Field(default=None, ge=0)
    declared_expenses: float | None = Field(default=None, ge=0)
    declared_debt_payment: float | None = Field(default=None, ge=0)
    applicant_role: ApplicantRole | None = None
    collateral_asset_id: int | None = None
    bki_consent: bool | None = None


class ApplicationCreate(ApplicationUpdate):
    product_id: str
    client_snapshot: dict = Field(default_factory=dict)
    credit_snapshot: dict = Field(default_factory=dict)


class ClientBrief(ORM):
    id: str
    name: str
    legal_form: str


class ClientRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_name: str = Field(min_length=3, max_length=160)
    name: str = Field(min_length=2, max_length=200)
    inn: str = Field(pattern=r"^(?:\d{10}|\d{12})$")
    ogrn: str = Field(pattern=r"^(?:\d{13}|\d{15})$")
    activity: str = Field(min_length=2, max_length=200)
    registration_date: str = Field(min_length=8, max_length=10)
    legal_form: Literal["ip", "ooo"]


class AssetOut(ORM):
    id: int
    kind: str
    description: str
    market_value: float


class ClientOut(ORM):
    id: str
    inn: str
    legal_form: str
    name: str
    okved: str
    tax_regime: str
    has_alfa_account: bool
    owner_name: str
    owner_age: int | None
    ogrn: str | None
    registration_date: str | None
    phone: str | None
    assets: list[AssetOut]


class StatusChangeOut(ORM):
    from_status: str | None
    to_status: str
    actor: str
    reason: str | None
    created_at: datetime


class SourceOut(ORM):
    source: str
    status: str
    duration_ms: int
    created_at: datetime


class DecisionOut(ORM):
    outcome: str
    amount: float | None
    term_months: int | None
    rate: float | None
    monthly_payment: float | None
    reasons: list[str]
    options: list[dict]
    created_at: datetime


class DecisionDetailOut(DecisionOut):
    pd: float | None
    risk_class: str | None
    factors: list[dict]
    model_version: str | None


class DocumentOut(ORM):
    id: int
    kind: str
    filename: str
    content_type: str | None
    size_bytes: int
    created_at: datetime


class AcceptOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option: int = Field(ge=0)


class ApplicationBrief(ORM):
    id: int
    client_id: str
    status: str
    product_id: str | None
    amount: float | None
    term_months: int | None
    client_snapshot: dict
    credit_snapshot: dict
    created_at: datetime
    updated_at: datetime


class ApplicationOut(ApplicationBrief):
    purpose: str | None
    declared_revenue: float | None
    declared_expenses: float | None
    declared_debt_payment: float | None
    applicant_role: str | None
    collateral_asset_id: int | None
    bki_consent: bool
    info_rounds: int
    issues: list[str]
    decision: DecisionDetailOut | None
    accepted_option: dict | None
    history: list[StatusChangeOut]
    sources: list[SourceOut]
    documents: list[DocumentOut]


class SourceDetailOut(SourceOut):
    payload: dict | None


class CheckOut(ORM):
    round: int
    kind: str
    code: str
    message: str
    data: dict
    created_at: datetime


Status = Literal[
    "draft", "submitted", "checking", "needs_info", "scoring",
    "approved", "counteroffer", "declined", "issued", "closed", "withdrawn",
]


class BankApplicationBrief(ORM):
    id: int
    client: ClientBrief
    status: str
    product_id: str | None
    amount: float | None
    term_months: int | None
    issues: list[str]
    decision: DecisionOut | None
    created_at: datetime
    updated_at: datetime


class ProcessingOut(ORM):
    id: int
    status: str
    info_rounds: int
    history: list[StatusChangeOut]
    sources: list[SourceDetailOut]
    checks: list[CheckOut]
    decisions: list[DecisionDetailOut]


class BankApplicationOut(ProcessingOut):
    client: ClientOut
    product_id: str | None
    amount: float | None
    term_months: int | None
    purpose: str | None
    declared_revenue: float | None
    declared_expenses: float | None
    declared_debt_payment: float | None
    applicant_role: str | None
    collateral_asset_id: int | None
    accepted_option: dict | None
    created_at: datetime
    updated_at: datetime
