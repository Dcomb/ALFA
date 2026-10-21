from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ClientBrief(ORM):
    id: str
    name: str
    legal_form: str


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
    assets: list[AssetOut]


class StatusChangeOut(ORM):
    from_status: str | None
    to_status: str
    actor: str
    reason: str | None
    created_at: datetime


class ApplicationBrief(ORM):
    id: int
    status: str
    product_id: str | None
    amount: float | None
    term_months: int | None
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
    history: list[StatusChangeOut]
