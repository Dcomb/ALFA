from .schemas import ClientProfile

DEMO_CLIENTS = {
    c.client_id: c for c in [
        ClientProfile(
            client_id='demo_cafe', legal_form='ip', business_age_months=14, owner_age=31,
            monthly_revenue=1200000, monthly_expenses=950000,
        ),
        ClientProfile(
            client_id='demo_logistics', legal_form='ooo', business_age_months=48,
            monthly_revenue=8000000, monthly_expenses=6500000, existing_monthly_debt=300000,
            has_collateral=True, collateral_value=20000000,
        ),
        ClientProfile(
            client_id='demo_newbie', legal_form='ip', business_age_months=5, owner_age=24,
            monthly_revenue=400000, monthly_expenses=330000,
        ),
    ]
}


def get_client(client_id):
    return DEMO_CLIENTS.get(client_id)
