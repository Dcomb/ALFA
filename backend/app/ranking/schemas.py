from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

NeedTag = Literal[
    'cash_gap', 'working_capital', 'investment', 'refinancing',
    'vehicle', 'real_estate', 'tender', 'small_expenses', 'any',
]


class ClientProfile(BaseModel):
    client_id: str
    legal_form: Literal['ip', 'ooo']
    business_age_months: int = Field(ge=0)
    owner_age: Optional[int] = None
    monthly_revenue: float = Field(ge=0)
    monthly_expenses: float = Field(ge=0)
    existing_monthly_debt: float = Field(default=0, ge=0)
    has_collateral: bool = False
    collateral_value: float = Field(default=0, ge=0)
    in_msp_registry: bool = True
    has_alfa_account: bool = True
    delinquency_180d: bool = False


class Need(BaseModel):
    purpose: Optional[NeedTag] = None
    amount: Optional[float] = Field(default=None, gt=0)
    term_months: Optional[int] = Field(default=None, gt=0)


class RecommendRequest(BaseModel):
    client_id: Optional[str] = None
    client: Optional[ClientProfile] = None
    need: Optional[Need] = None
    top_k: int = Field(default=3, ge=1, le=13)

    @model_validator(mode='after')
    def client_given(self):
        if self.client is None and self.client_id is None:
            raise ValueError('нужен client или client_id')
        return self


class Option(BaseModel):
    amount: float
    term_months: int
    monthly_payment: Optional[float]
    note: str


class Recommendation(BaseModel):
    product_id: str
    name: str
    score: float
    approval_prob: float
    rate: Optional[float]
    amount: Optional[float]
    max_amount: Optional[float]
    term_months: Optional[int]
    monthly_payment: Optional[float]
    overpayment: Optional[float]
    reasons: list[str]
    warnings: list[str] = []
    alternatives: list[Option] = []


class Rejected(BaseModel):
    product_id: str
    name: str
    reason: str
    hint: Optional[str] = None
    alternatives: list[str] = []


class Change(BaseModel):
    kind: Literal['amount', 'term', 'account', 'collateral', 'wait']
    text: str


class Concession(BaseModel):
    product_id: str
    name: str
    changes: list[Change]
    feasible_now: bool
    coverage: float
    offer: Recommendation


class RecommendResponse(BaseModel):
    client_id: str
    recommendations: list[Recommendation]
    rejected: list[Rejected]
    concessions: list[Concession] = []


class ScoreRequest(BaseModel):
    client_id: Optional[str] = None
    client: Optional[ClientProfile] = None
    product_id: str
    amount: float = Field(gt=0)
    term_months: int = Field(gt=0)


class ScoreResponse(BaseModel):
    product_id: str
    approval_prob: float
    rate: Optional[float]
    stub: bool = True


class CalcRequest(BaseModel):
    amount: float = Field(gt=0)
    annual_rate: float = Field(ge=0)
    term_months: int = Field(gt=0)


class CalcResponse(BaseModel):
    monthly_payment: float
    total_payment: float
    overpayment: float


class LimitRequest(BaseModel):
    client_id: Optional[str] = None
    client: Optional[ClientProfile] = None
    annual_rate: float = Field(ge=0)
    term_months: int = Field(gt=0)


class LimitResponse(BaseModel):
    free_cash_flow: float
    max_monthly_payment: float
    max_amount: float
