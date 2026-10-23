import json

import pytest
from pydantic import ValidationError

from app.policy import POLICY, POLICY_PATH, Policy


def raw_policy():
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def test_policy_loads():
    assert POLICY.affordability.dscr > 1
    assert POLICY.verification.max_info_rounds >= 0


def test_unknown_field_is_rejected():
    data = raw_policy()
    data["verification"]["revenue_tolerence"] = 0.3
    with pytest.raises(ValidationError):
        Policy.model_validate(data)


def test_missing_field_is_rejected():
    data = raw_policy()
    del data["affordability"]["dscr"]
    with pytest.raises(ValidationError):
        Policy.model_validate(data)


@pytest.mark.parametrize("section, name, value", [
    ("affordability", "dscr", 0.9),
    ("affordability", "collateral_ltv", 1.5),
    ("verification", "revenue_tolerance", -0.1),
    ("concessions", "max_variants", 0),
])
def test_out_of_range_is_rejected(section, name, value):
    data = raw_policy()
    data[section][name] = value
    with pytest.raises(ValidationError):
        Policy.model_validate(data)
