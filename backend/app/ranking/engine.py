import math

from . import calculator as calc
from .catalog import load_catalog, products
from .schemas import Change, Concession, Need, Option, Recommendation, Rejected, RecommendResponse
from .scoring_stub import get_score
from app.policy import POLICY

DEFAULT_TERM = POLICY.default_term_months
FIT_MATCH = POLICY.concessions.fit_match
MAX_CHANGES = POLICY.concessions.max_changes
MAX_CONCESSIONS = POLICY.concessions.max_variants
CLEAN_HISTORY_MONTHS = POLICY.concessions.clean_history_months
LOAN_TYPES = ('term_loan', 'line', 'revolving')
SPECIAL_PURPOSE = set(POLICY.need_match.special_purposes)


def rub(x):
    return f'{x:,.0f}'.replace(',', ' ') + ' ₽'


def eligibility_problems(client, product, need=None):
    problems = []
    min_age = product.get('business_age_months_min', 9)
    if client.business_age_months < min_age:
        wait = min_age - client.business_age_months
        problems.append((
            f'бизнесу {client.business_age_months} мес., нужно от {min_age}',
            f'станет доступен через {wait} мес.',
            ('wait', wait),
        ))
    owner_age = product.get('owner_age')
    if owner_age and client.owner_age is not None and not owner_age[0] <= client.owner_age <= owner_age[1]:
        problems.append((f'возраст владельца вне диапазона {owner_age[0]}-{owner_age[1]}', None, ('immutable', None)))
    if product.get('requires_own_collateral') and not client.has_collateral:
        if need and need.amount:
            hint = f'для {rub(need.amount)} нужен залог стоимостью от {rub(need.amount / calc.COLLATERAL_LTV)}'
        else:
            hint = f'залог учитывается в размере {calc.COLLATERAL_LTV:.0%} его стоимости'
        problems.append(('нужен залог', hint, ('collateral', None)))
    if product.get('requires_alfa_account') and not client.has_alfa_account:
        problems.append((
            'нужен расчетный счет в Альфа-Банке',
            'откройте расчетный счет в Альфа-Банке, и продукт станет доступен',
            ('account', None),
        ))
    if product['id'] == 'msp_state_support':
        if not client.in_msp_registry:
            problems.append((
                'нет в реестре МСП',
                'проверьте сведения о компании в реестре МСП на rmsp.nalog.ru',
                ('immutable', None),
            ))
        if client.delinquency_180d:
            problems.append((
                'были просрочки за последние 180 дней',
                'станет доступен после 180 дней без просрочек',
                ('clean_history', CLEAN_HISTORY_MONTHS),
            ))
    return problems


def term_range(product):
    if product.get('term') is None:
        return None
    lo, hi = product['term']
    return lo or 1, hi or DEFAULT_TERM


def pick_term(product, need):
    rng = term_range(product)
    if rng is None:
        return need.term_months if need and need.term_months else DEFAULT_TERM
    lo, hi = rng
    default = min(hi, DEFAULT_TERM) if product['type'] == 'term_loan' else hi
    t = need.term_months if need and need.term_months else default
    return min(max(t, lo), hi)


def amount_bounds(product):
    a = product.get('amount') or [None, None]
    return a[0] or 0, a[1] or float('inf')


def need_match(product, need):
    tags = product['need_tags']
    if need is None or need.purpose is None:
        weights = POLICY.need_match
        return weights.unknown_purpose_special if SPECIAL_PURPOSE & set(tags) else weights.unknown_purpose
    if need.purpose in tags:
        return POLICY.need_match.exact
    if 'any' in tags:
        return POLICY.need_match.any_purpose
    return POLICY.need_match.mismatch


def loan_cap(client, product, rate, term):
    _, amax = amount_bounds(product)
    cap = min(amax, calc.max_loan_amount(client, rate, term))
    if product.get('requires_own_collateral'):
        cap = min(cap, calc.collateral_cap(client))
    return cap


def shortest_term(client, product, rate, term, target):
    rng = term_range(product)
    if rng is None:
        return None
    for t in range(term + 1, rng[1] + 1):
        if loan_cap(client, product, rate, t) >= target:
            return t
    return None


def term_warnings(product, need, term):
    if not (need and need.term_months) or need.term_months == term:
        return []
    text = f'срок {need.term_months} мес. недоступен, взят {term} мес.'
    rng = term_range(product)
    if rng:
        text += f' (у продукта от {rng[0]} до {rng[1]} мес.)'
    return [text]


def cash_flow_problem(client, product, amin, rate):
    collateral = calc.collateral_cap(client)
    if product.get('requires_own_collateral') and collateral < amin:
        return (
            f'залог покрывает {rub(collateral)}, минимум продукта {rub(amin)}',
            f'нужен залог стоимостью от {rub(amin / calc.COLLATERAL_LTV)}',
        )
    rng = term_range(product)
    t = rng[1] if rng else DEFAULT_TERM
    available = calc.max_loan_amount(client, rate, t)
    shortfall = calc.annuity_payment(amin, rate, t) - calc.max_monthly_payment(client)
    return (
        f'по денежному потоку доступно {rub(available)}, минимум продукта {rub(amin)}',
        f'для минимальной суммы на {t} мес. свободный денежный поток должен быть больше на {rub(shortfall)} в месяц',
    )


def extend_option(client, product, rate, term, requested, cap):
    t = shortest_term(client, product, rate, term, requested)
    if t is not None:
        amount, note = requested, f'вся запрошенная сумма при сроке {t} мес.'
    else:
        rng = term_range(product)
        if rng is None or rng[1] <= term:
            return None
        t = rng[1]
        amount = loan_cap(client, product, rate, t)
        if amount <= cap + 1:
            return None
        note = f'максимальная сумма при сроке {t} мес.'
    return Option(
        amount=round(amount, 2),
        term_months=t,
        monthly_payment=round(calc.annuity_payment(amount, rate, t), 2),
        note=note,
    )


def build_offer(client, product, need):
    term = pick_term(product, need)
    amin, amax = amount_bounds(product)
    requested = need.amount if need and need.amount else None
    offer = {'term_months': term, 'rate': None, 'amount': None, 'max_amount': None,
             'monthly_payment': None, 'overpayment': None, 'notes': [], 'warnings': [], 'alternatives': []}

    if product['type'] in LOAN_TYPES:
        offer['warnings'].extend(term_warnings(product, need, term))
        if requested is not None and requested < amin:
            offer['warnings'].append(f'минимальная сумма продукта {rub(amin)}, запрошено {rub(requested)}')

        if product['id'] == 'overdraft':
            cap = min(amax, calc.overdraft_limit(client))
            if cap < amin:
                share = calc.OVERDRAFT_TURNOVER_SHARE
                return None, (
                    f'лимит овердрафта {rub(cap)}, минимум продукта {rub(amin)}',
                    f'лимит равен {share:.0%} месячной выручки, нужна выручка от {rub(amin / share)} в месяц',
                )
        else:
            cap = loan_cap(client, product, product['rate_from'], term)
            if cap < amin:
                term = shortest_term(client, product, product['rate_from'], term, amin)
                if term is None:
                    return None, cash_flow_problem(client, product, amin, product['rate_from'])
                cap = loan_cap(client, product, product['rate_from'], term)

        amount = max(min(requested, cap) if requested else cap, amin)
        score = get_score(client, product, amount, term)
        rate = score.rate

        if product['id'] == 'overdraft':
            interest, fee = calc.overdraft_cost(amount, rate)
            offer['overpayment'] = interest + fee
            offer['notes'].append(f'проценты за полный транш {rub(interest)}, комиссия за подключение {rub(fee)}')
        else:
            cap = loan_cap(client, product, rate, term)
            if cap < amin:
                term = shortest_term(client, product, rate, term, amin)
                if term is None:
                    return None, cash_flow_problem(client, product, amin, rate)
                cap = loan_cap(client, product, rate, term)
            if term != offer['term_months']:
                offer['warnings'].append(f'срок увеличен до {term} мес., иначе платеж не укладывается в денежный поток')
            amount = min(amount, cap)
            loan = calc.loan_offer(amount, rate, term)
            offer['monthly_payment'] = loan['monthly_payment']
            offer['overpayment'] = loan['overpayment']
            if requested and amount < requested:
                option = extend_option(client, product, rate, term, requested, cap)
                if option:
                    offer['alternatives'].append(option)

        offer.update(rate=rate, term_months=term, amount=round(amount, 2), max_amount=round(cap, 2))
        return (offer, score), None

    if product['type'] == 'card':
        cap = min(amax, calc.overdraft_limit(client))
        amount = min(requested, cap) if requested else cap
        score = get_score(client, product, amount, term)
        offer.update(amount=round(amount, 2), max_amount=round(cap, 2))
        return (offer, score), None

    amount = requested or 0
    score = get_score(client, product, amount or 1.0, term)
    offer.update(amount=amount or None, rate=product.get('rate_from'))
    if product['type'] == 'guarantee' and amount:
        offer['overpayment'] = calc.guarantee_cost(amount, product['rate_from'], term)
    return (offer, score), None


def make_recommendation(product, need, offer, score):
    tag_names = load_catalog()['meta']['need_tags']
    match = need_match(product, need)
    fit = 1.0
    if need and need.amount and offer['max_amount'] is not None:
        fit = min(1.0, offer['max_amount'] / need.amount)
    final = match * score.approval_prob * fit

    reasons = []
    if need and need.purpose and need.purpose in product['need_tags']:
        reasons.append(f'подходит под цель: {tag_names[need.purpose]}')
    reasons.append(f'вероятность одобрения {score.approval_prob:.0%}')
    if fit < 1:
        reasons.append(f'доступно до {rub(offer["max_amount"])} из запрошенных {rub(need.amount)}')
    if offer['monthly_payment']:
        suffix = '' if need and need.amount else ' при максимальной сумме'
        reasons.append(f'платеж {rub(offer["monthly_payment"])} в месяц{suffix}')
    if product.get('highlight'):
        reasons.append(product['highlight'])
    reasons.extend(offer['notes'])

    return Recommendation(
        product_id=product['id'], name=product['name'], score=round(final, 4),
        approval_prob=score.approval_prob, rate=offer['rate'], amount=offer['amount'],
        max_amount=offer['max_amount'], term_months=offer['term_months'],
        monthly_payment=offer['monthly_payment'], overpayment=offer['overpayment'],
        reasons=reasons, warnings=offer['warnings'], alternatives=offer['alternatives'],
    )


def matches_purpose(product, need):
    return need is None or need.purpose is None or need_match(product, need) >= FIT_MATCH


def fits(rec, product, need):
    if not matches_purpose(product, need):
        return False
    return not (need and need.amount) or (rec.amount or 0) >= need.amount - 1


def apply_fixes(client, product, need, fixes):
    update, changes, wait = {}, [], 0
    for kind, value in fixes:
        if kind == 'immutable':
            return None
        if kind == 'wait':
            wait = max(wait, value)
        if kind == 'clean_history':
            wait = max(wait, value)
            update['delinquency_180d'] = False
        if kind == 'account':
            update['has_alfa_account'] = True
            changes.append(Change(kind='account', text='открыть расчетный счет в Альфа-Банке'))
    if product.get('requires_own_collateral'):
        amin, _ = amount_bounds(product)
        needed = max(need.amount if need and need.amount else 0, amin) / calc.COLLATERAL_LTV
        if not client.has_collateral or client.collateral_value < needed:
            update.update(has_collateral=True, collateral_value=needed)
            changes.append(Change(kind='collateral', text=f'предоставить залог стоимостью от {rub(needed)}'))
    if wait:
        update['business_age_months'] = client.business_age_months + wait
        changes.append(Change(kind='wait', text=f'подождать {wait} мес., пока продукт станет доступен'))
    return client.model_copy(update=update), changes


def make_concession(product, need, offer, score, base_changes):
    changes = list(base_changes)
    requested_term = need.term_months if need and need.term_months else pick_term(product, need)
    if need and need.amount and offer['amount'] is not None and offer['amount'] < need.amount - 1:
        changes.append(Change(kind='amount', text=f'сумма {rub(offer["amount"])} вместо {rub(need.amount)}'))
    if offer['term_months'] != requested_term:
        changes.append(Change(kind='term', text=f'срок {offer["term_months"]} мес. вместо {requested_term}'))
    if not changes or len(changes) > MAX_CHANGES:
        return None
    coverage = 1.0
    if need and need.amount and offer['amount'] is not None:
        coverage = min(1.0, offer['amount'] / need.amount)
    return Concession(
        product_id=product['id'], name=product['name'], changes=changes,
        feasible_now=not any(c.kind in ('wait', 'collateral') for c in changes),
        coverage=round(coverage, 4), offer=make_recommendation(product, need, offer, score),
    )


def concession_variants(client, product, need):
    if not matches_purpose(product, need):
        return []
    fixed = apply_fixes(client, product, need, [p[2] for p in eligibility_problems(client, product, need)])
    if fixed is None:
        return []
    fixed_client, base_changes = fixed
    built, problem = build_offer(fixed_client, product, need)
    if problem is not None:
        return []
    offer, score = built
    variants = [make_concession(product, need, offer, score, base_changes)]
    for option in offer['alternatives']:
        longer = Need(purpose=need.purpose if need else None, amount=option.amount, term_months=option.term_months)
        built, problem = build_offer(fixed_client, product, longer)
        if problem is None:
            variants.append(make_concession(product, need, *built, base_changes))
    return [v for v in variants if v is not None]


def concession_key(c):
    overpayment = c.offer.overpayment if c.offer.overpayment is not None else math.inf
    return not c.feasible_now, -c.coverage, len(c.changes), overpayment


def find_concessions(client, need):
    best = []
    for product in products():
        variants = concession_variants(client, product, need)
        if variants:
            best.append(min(variants, key=concession_key))
    return sorted(best, key=concession_key)[:MAX_CONCESSIONS]


def recommend(client, need=None, top_k=3):
    recs, rejected, tags, by_id = [], [], {}, {}

    for product in products():
        by_id[product['id']] = product
        tags[product['id']] = set(product['need_tags']) - {'any'}
        problems = eligibility_problems(client, product, need)
        if problems:
            reason = '; '.join(p[0] for p in problems)
            hint = '; '.join(p[1] for p in problems if p[1]) or None
        else:
            built, problem = build_offer(client, product, need)
            reason, hint = problem if problem else (None, None)
        if reason is not None:
            rejected.append(Rejected(product_id=product['id'], name=product['name'], reason=reason, hint=hint))
            continue
        recs.append(make_recommendation(product, need, *built))

    recs.sort(key=lambda r: (-r.score, r.overpayment if r.overpayment is not None else math.inf))
    for r in rejected:
        r.alternatives = [x.product_id for x in recs if tags[x.product_id] & tags[r.product_id]][:3]

    concessions = []
    if not any(fits(r, by_id[r.product_id], need) for r in recs):
        concessions = find_concessions(client, need)

    return RecommendResponse(
        client_id=client.client_id, recommendations=recs[:top_k],
        rejected=rejected, concessions=concessions,
    )
