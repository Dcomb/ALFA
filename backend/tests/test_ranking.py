import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ranking import calculator as calc
from app.ranking.clients import get_client
from app.ranking.inference import recommend_for_client

client = TestClient(app)

CAFE = get_client('demo_cafe').model_dump()


def post(path, body):
    return client.post(f'/ranking{path}', json=body)


def test_products():
    assert len(client.get('/ranking/products').json()) == 13


def test_annuity_roundtrip():
    payment = calc.annuity_payment(1_000_000, 15, 24)
    assert calc.principal_from_payment(payment, 15, 24) == pytest.approx(1_000_000)


def test_zero_rate():
    assert calc.annuity_payment(120_000, 0, 12) == pytest.approx(10_000)


def test_cash_gap_gives_overdraft_first():
    r = post('/recommend', {'client_id': 'demo_cafe', 'need': {'purpose': 'cash_gap'}})
    assert r.status_code == 200
    assert r.json()['recommendations'][0]['product_id'] == 'overdraft'


def test_payment_fits_cash_flow():
    r = post('/recommend', {'client_id': 'demo_cafe', 'need': {'purpose': 'investment', 'amount': 5_000_000}})
    limit = calc.max_monthly_payment(get_client('demo_cafe'))
    for rec in r.json()['recommendations']:
        if rec['monthly_payment'] is not None:
            assert rec['monthly_payment'] <= limit + 1


def test_newbie_rejected_by_business_age():
    d = post('/recommend', {'client_id': 'demo_newbie'}).json()
    rejected = {x['product_id'] for x in d['rejected']}
    assert 'overdraft' in rejected
    assert all(rec['product_id'] not in rejected for rec in d['recommendations'])


def test_no_collateral_no_secured():
    d = post('/recommend', {'client_id': 'demo_cafe', 'top_k': 13}).json()
    ids = {rec['product_id'] for rec in d['recommendations']}
    assert 'loan_secured' not in ids


def test_every_rejected_has_reason():
    d = post('/recommend', {'client_id': 'demo_newbie', 'top_k': 13}).json()
    assert d['rejected']
    assert all(x['reason'] for x in d['rejected'])


def test_unknown_client_404():
    assert post('/recommend', {'client_id': 'nope'}).status_code == 404


def test_missing_client_422():
    assert post('/recommend', {}).status_code == 422


@pytest.mark.parametrize('need', [
    {'purpose': 'unknown_purpose'},
    {'term_months': 0},
    {'amount': -1},
])
def test_bad_need_422(need):
    assert post('/recommend', {'client_id': 'demo_cafe', 'need': need}).status_code == 422


def test_negative_revenue_422():
    assert post('/recommend', {'client': {**CAFE, 'monthly_revenue': -1}}).status_code == 422


def test_zero_revenue_no_loans():
    r = post('/recommend', {'client': {**CAFE, 'monthly_revenue': 0, 'monthly_expenses': 0}, 'top_k': 13})
    assert r.status_code == 200
    for rec in r.json()['recommendations']:
        assert not rec['monthly_payment']


def test_expenses_above_revenue():
    r = post('/recommend', {'client': {**CAFE, 'monthly_expenses': CAFE['monthly_revenue'] * 2}, 'top_k': 13})
    assert r.status_code == 200
    for rec in r.json()['recommendations']:
        assert not rec['monthly_payment']


def test_huge_amount():
    r = post('/recommend', {'client_id': 'demo_logistics', 'need': {'purpose': 'working_capital', 'amount': 1e18}})
    assert r.status_code == 200


def test_calculator_payment():
    r = post('/calculator/payment', {'amount': 1_000_000, 'annual_rate': 15, 'term_months': 24})
    assert r.status_code == 200
    assert r.json()['overpayment'] > 0


def test_calculator_limit():
    r = post('/calculator/limit', {'client_id': 'demo_logistics', 'annual_rate': 18, 'term_months': 36})
    assert r.status_code == 200
    assert r.json()['max_amount'] > 0


def test_inference_returns_dict():
    d = recommend_for_client('demo_cafe', purpose='cash_gap')
    assert d['recommendations'][0]['product_id'] == 'overdraft'


def test_inference_unknown_client():
    with pytest.raises(KeyError):
        recommend_for_client('nope')


def recommend_all(client_body, need):
    r = post('/recommend', {'client': client_body, 'need': need, 'top_k': 13})
    assert r.status_code == 200
    return r.json()


POOR_CAFE = {**CAFE, 'has_alfa_account': False, 'monthly_expenses': 1_180_000}


def test_rejected_by_business_age_has_wait_hint():
    d = post('/recommend', {'client_id': 'demo_newbie'}).json()
    overdraft = next(x for x in d['rejected'] if x['product_id'] == 'overdraft')
    assert overdraft['hint'] == 'станет доступен через 4 мес.'


def test_rejected_points_to_available_alternatives():
    d = post('/recommend', {'client_id': 'demo_newbie', 'top_k': 13}).json()
    available = {x['product_id'] for x in d['recommendations']}
    overdraft = next(x for x in d['rejected'] if x['product_id'] == 'overdraft')
    assert overdraft['alternatives']
    assert set(overdraft['alternatives']) <= available


def test_no_alfa_account_hint():
    d = recommend_all({**CAFE, 'has_alfa_account': False}, {'purpose': 'cash_gap'})
    overdraft = next(x for x in d['rejected'] if x['product_id'] == 'overdraft')
    assert 'откройте расчетный счет' in overdraft['hint']


def test_collateral_hint_uses_requested_amount():
    d = recommend_all(CAFE, {'purpose': 'investment', 'amount': 1_000_000})
    secured = next(x for x in d['rejected'] if x['product_id'] == 'loan_secured')
    assert '2 000 000' in secured['hint']


def test_cash_flow_rejection_has_positive_shortfall():
    d = recommend_all(POOR_CAFE, {'purpose': 'working_capital', 'amount': 1_000_000})
    line = next(x for x in d['rejected'] if x['product_id'] == 'credit_line_unsecured')
    assert line['reason'].startswith('по денежному потоку')
    assert 'больше на' in line['hint'] and '-' not in line['hint']


def test_term_extended_instead_of_rejection():
    d = recommend_all(POOR_CAFE, {'purpose': 'refinancing', 'amount': 1_000_000})
    refinancing = next(x for x in d['recommendations'] if x['product_id'] == 'refinancing')
    assert refinancing['term_months'] > 36
    assert any('срок увеличен' in w for w in refinancing['warnings'])


def test_term_clamp_warning():
    d = recommend_all(CAFE, {'purpose': 'working_capital', 'amount': 500_000, 'term_months': 200})
    line = next(x for x in d['recommendations'] if x['product_id'] == 'credit_line_unsecured')
    assert line['term_months'] == 18
    assert any('срок 200 мес. недоступен' in w for w in line['warnings'])


def test_min_amount_warning():
    d = recommend_all(CAFE, {'purpose': 'working_capital', 'amount': 100_000})
    loan = next(x for x in d['recommendations'] if x['product_id'] == 'loan_any_purpose')
    assert loan['amount'] == 300_000
    assert any('минимальная сумма продукта' in w for w in loan['warnings'])


def test_longer_term_alternatives_fit_cash_flow():
    d = recommend_all(POOR_CAFE, {'purpose': 'working_capital', 'amount': 1_000_000})
    limit = calc.max_monthly_payment(get_client('demo_cafe').model_copy(update={'monthly_expenses': 1_180_000}))
    options = [(rec, opt) for rec in d['recommendations'] for opt in rec['alternatives']]
    assert options
    for rec, opt in options:
        assert opt['term_months'] > rec['term_months']
        assert opt['amount'] > rec['amount']
        assert opt['monthly_payment'] <= limit + 1


NEWBIE = get_client('demo_newbie').model_dump()


def concession_order(c):
    return not c['feasible_now'], -c['coverage'], len(c['changes'])


def test_no_concessions_when_something_fits():
    d = post('/recommend', {'client_id': 'demo_cafe', 'need': {'purpose': 'cash_gap'}}).json()
    assert d['concessions'] == []


def test_concessions_when_nothing_fits():
    d = recommend_all(NEWBIE, {'purpose': 'working_capital', 'amount': 2_000_000})
    concessions = d['concessions']
    assert 0 < len(concessions) <= 3
    assert len({c['product_id'] for c in concessions}) == len(concessions)
    for c in concessions:
        assert 0 < len(c['changes']) <= 2
        assert c['offer']['product_id'] == c['product_id']
    assert concessions == sorted(concessions, key=concession_order)


def test_waiting_is_not_feasible_now():
    d = recommend_all(NEWBIE, {'purpose': 'working_capital', 'amount': 2_000_000})
    for c in d['concessions']:
        if any(ch['kind'] in ('wait', 'collateral') for ch in c['changes']):
            assert not c['feasible_now']


def test_concession_offers_fit_cash_flow():
    d = recommend_all(POOR_CAFE, {'purpose': 'working_capital', 'amount': 1_000_000})
    limit = calc.max_monthly_payment(get_client('demo_cafe').model_copy(update={'monthly_expenses': 1_180_000}))
    assert d['concessions']
    for c in d['concessions']:
        if c['offer']['monthly_payment'] is not None:
            assert c['offer']['monthly_payment'] <= limit + 1


def test_immutable_requirement_never_conceded():
    d = recommend_all({**CAFE, 'owner_age': 70}, {'purpose': 'cash_gap', 'amount': 50_000_000})
    assert d['concessions']
    assert 'overdraft' not in {c['product_id'] for c in d['concessions']}


def test_account_concession():
    from app.ranking.catalog import get_product
    from app.ranking.engine import concession_variants
    from app.ranking.schemas import ClientProfile, Need
    client = ClientProfile(**{**CAFE, 'has_alfa_account': False})
    variants = concession_variants(client, get_product('overdraft'), Need(purpose='cash_gap', amount=300_000))
    assert variants
    assert any(ch.kind == 'account' for ch in variants[0].changes)
    assert variants[0].feasible_now


def test_rejected_lists_all_reasons():
    d = recommend_all(NEWBIE, {'purpose': 'investment'})
    secured = next(x for x in d['rejected'] if x['product_id'] == 'loan_secured')
    assert 'бизнесу' in secured['reason'] and 'нужен залог' in secured['reason']
