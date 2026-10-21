from .schemas import ClientProfile

DEMO_CLIENTS = {
    c.client_id: c for c in [
        ClientProfile(
            client_id='demo_cafe', legal_form='ip', business_age_months=14, owner_age=31,
            monthly_revenue=1_200_000, monthly_expenses=950_000,
        ),
        ClientProfile(
            client_id='demo_logistics', legal_form='ooo', business_age_months=48,
            monthly_revenue=8_000_000, monthly_expenses=6_500_000, existing_monthly_debt=300_000,
            has_collateral=True, collateral_value=20_000_000,
        ),
        ClientProfile(
            client_id='demo_newbie', legal_form='ip', business_age_months=5, owner_age=24,
            monthly_revenue=400_000, monthly_expenses=330_000,
        ),
    ]
}


def get_client(client_id):
    return DEMO_CLIENTS.get(client_id)
