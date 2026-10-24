from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

POLICY_PATH = Path(__file__).parent / "credit_policy.json"

Share = Field(gt=0, le=1)


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Affordability(Section):
    dscr: float = Field(gt=1)
    overdraft_turnover_share: float = Share
    collateral_ltv: float = Share
    reference_rate: float = Field(gt=0, lt=100)


class NeedMatch(Section):
    exact: float = Share
    any_purpose: float = Share
    unknown_purpose: float = Share
    unknown_purpose_special: float = Share
    mismatch: float = Share
    special_purposes: list[str]


class Concessions(Section):
    fit_match: float = Share
    max_changes: int = Field(ge=1)
    max_variants: int = Field(ge=1)
    clean_history_months: int = Field(ge=1)


class RiskClasses(Section):
    A: float = Share
    B: float = Share
    C: float = Share

    @model_validator(mode="after")
    def increasing(self):
        if not self.A < self.B < self.C:
            raise ValueError("пороги классов риска должны возрастать: A < B < C")
        return self


class RiskWeights(Section):
    C: float = Share
    D: float = Share

    @model_validator(mode="after")
    def decreasing(self):
        if self.D > self.C:
            raise ValueError("вес класса D в подборе не может быть больше веса класса C")
        return self


class Explanation(Section):
    min_factor_points: float = Field(ge=0)


class Verification(Section):
    revenue_tolerance: float = Field(ge=0, lt=1)
    debt_tolerance: float = Field(ge=0, lt=1)
    max_current_overdue_days: int = Field(ge=0)
    max_info_rounds: int = Field(ge=0)


class Policy(Section):
    default_term_months: int = Field(gt=0)
    affordability: Affordability
    need_match: NeedMatch
    concessions: Concessions
    risk_classes: RiskClasses
    risk_weights: RiskWeights
    explanation: Explanation
    verification: Verification


POLICY = Policy.model_validate_json(POLICY_PATH.read_text(encoding="utf-8"))
