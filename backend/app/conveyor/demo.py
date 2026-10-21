from .models import Asset, Client

DEMO_CLIENTS = [
    {
        "id": "demo_cafe",
        "inn": "000010100195",
        "legal_form": "ip",
        "name": "ИП Соколова А. В., кафе",
        "okved": "56.10",
        "tax_regime": "usn_15",
        "has_alfa_account": True,
        "owner_name": "Соколова Анна Викторовна",
        "owner_age": 31,
        "assets": [],
    },
    {
        "id": "demo_logistics",
        "inn": "0000201003",
        "legal_form": "ooo",
        "name": "ООО «Северный путь», грузоперевозки",
        "okved": "49.41",
        "tax_regime": "osno",
        "has_alfa_account": True,
        "owner_name": "Громов Дмитрий Сергеевич",
        "owner_age": 45,
        "assets": [
            {"kind": "real_estate", "description": "складское помещение 600 м²", "market_value": 20_000_000},
            {"kind": "vehicle", "description": "седельный тягач, 2021 г.", "market_value": 7_500_000},
        ],
    },
    {
        "id": "demo_newbie",
        "inn": "000030100210",
        "legal_form": "ip",
        "name": "ИП Лебедев К. А., интернет-магазин",
        "okved": "47.91",
        "tax_regime": "usn_6",
        "has_alfa_account": True,
        "owner_name": "Лебедев Кирилл Андреевич",
        "owner_age": 24,
        "assets": [],
    },
]


def seed_demo_clients(session):
    for data in DEMO_CLIENTS:
        if session.get(Client, data["id"]) is not None:
            continue
        fields = {key: value for key, value in data.items() if key != "assets"}
        client = Client(**fields, assets=[Asset(**asset) for asset in data["assets"]])
        session.add(client)
    session.commit()
