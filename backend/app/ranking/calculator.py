DSCR = 1.25
OVERDRAFT_TURNOVER_SHARE = 0.3
COLLATERAL_LTV = 0.5


def annuity_payment(principal, annual_rate, months):
    r = annual_rate / 100 / 12
    if r == 0:
        return principal / months
    return principal * r / (1 - (1 + r) ** -months)


def principal_from_payment(payment, annual_rate, months):
    if payment <= 0:
        return 0.0
    r = annual_rate / 100 / 12
    if r == 0:
        return payment * months
    return payment * (1 - (1 + r) ** -months) / r


def loan_offer(principal, annual_rate, months):
    payment = annuity_payment(principal, annual_rate, months)
    total = payment * months
    return {
        'monthly_payment': round(payment, 2),
        'total_payment': round(total, 2),
        'overpayment': round(total - principal, 2),
    }


def free_cash_flow(client):
    return client.monthly_revenue - client.monthly_expenses - client.existing_monthly_debt


def max_monthly_payment(client, dscr=DSCR):
    operating = client.monthly_revenue - client.monthly_expenses
    return max(operating / dscr - client.existing_monthly_debt, 0.0)


def max_loan_amount(client, annual_rate, months, dscr=DSCR):
    return principal_from_payment(max_monthly_payment(client, dscr), annual_rate, months)


def collateral_cap(client, ltv=COLLATERAL_LTV):
    return client.collateral_value * ltv if client.has_collateral else 0.0


def overdraft_limit(client, share=OVERDRAFT_TURNOVER_SHARE):
    return client.monthly_revenue * share


def overdraft_cost(limit, annual_rate, tranche_days=60, fee_share=0.01, fee_min=10000):
    interest = limit * annual_rate / 100 * tranche_days / 365
    fee = max(limit * fee_share, fee_min)
    return round(interest, 2), round(fee, 2)


def guarantee_cost(amount, annual_rate, months):
    return round(amount * annual_rate / 100 * months / 12, 2)
