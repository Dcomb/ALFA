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
            monthly_revenue=380000, monthly_expenses=330000, existing_monthly_debt=12000,
        ),
        ClientProfile(
            client_id='demo_unstable_bki', legal_form='ip', business_age_months=43, owner_age=38,
            monthly_revenue=900000, monthly_expenses=720000,
        ),
        ClientProfile(
            client_id='demo_liquidated', legal_form='ooo', business_age_months=88, owner_age=52,
            monthly_revenue=3200000, monthly_expenses=2750000, existing_monthly_debt=80000,
        ),
        ClientProfile(
            client_id='demo_overdue', legal_form='ip', business_age_months=61, owner_age=34,
            monthly_revenue=700000, monthly_expenses=610000, existing_monthly_debt=45000,
            delinquency_180d=True,
        ),
        ClientProfile(
            client_id='demo_disqualified', legal_form='ooo', business_age_months=88, owner_age=47,
            monthly_revenue=3200000, monthly_expenses=2750000, existing_monthly_debt=80000,
        ),
        ClientProfile(
            client_id='demo_gray', legal_form='ip', business_age_months=42, owner_age=41,
            monthly_revenue=1100000, monthly_expenses=940000, existing_monthly_debt=30000,
        ),
        ClientProfile(
            client_id='demo_gray_ooo', legal_form='ooo', business_age_months=42, owner_age=50,
            monthly_revenue=2500000, monthly_expenses=2150000, existing_monthly_debt=30000,
            has_collateral=True, collateral_value=4000000,
        ),
    ]
}


def register_client_profile(profile: ClientProfile) -> None:
    """Добавить профиль зарегистрированного клиента в runtime прототипа."""
    DEMO_CLIENTS[profile.client_id] = profile


def get_client(client_id):
    profile = DEMO_CLIENTS.get(client_id)
    if profile is not None:
        return profile

    # Зарегистрированные кабинеты хранятся в PostgreSQL. Финансовые поля
    # появятся после заполнения заявки, поэтому до этого используем нули,
    # а не данные другого демо-клиента.
    try:
        from app.conveyor.db import SessionLocal
        from app.conveyor.models import Client

        with SessionLocal() as session:
            stored = session.get(Client, client_id)
            if stored is None:
                return None
            profile = ClientProfile(
                client_id=stored.id,
                legal_form=stored.legal_form,
                business_age_months=12,
                owner_age=stored.owner_age,
                monthly_revenue=0,
                monthly_expenses=0,
                has_collateral=bool(stored.assets),
                collateral_value=sum(asset.market_value for asset in stored.assets),
                has_alfa_account=stored.has_alfa_account,
            )
            DEMO_CLIENTS[client_id] = profile
            return profile
    except Exception:
        return None
