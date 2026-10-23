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
    {
        "id": "demo_unstable_bki",
        "inn": "000040100499",
        "legal_form": "ip",
        "name": "ИП Орлова М. П., салон красоты (БКИ не отвечает)",
        "okved": "96.02",
        "tax_regime": "usn_6",
        "has_alfa_account": True,
        "owner_name": "Орлова Мария Павловна",
        "owner_age": 38,
        "assets": [],
    },
    {
        "id": "demo_liquidated",
        "inn": "0000501007",
        "legal_form": "ooo",
        "name": "ООО «Вектор», строительство (ликвидирована)",
        "okved": "41.20",
        "tax_regime": "osno",
        "has_alfa_account": True,
        "owner_name": "Сидоров Павел Игоревич",
        "owner_age": 52,
        "assets": [],
    },
    {
        "id": "demo_overdue",
        "inn": "000060100440",
        "legal_form": "ip",
        "name": "ИП Ковалёв А. С., автосервис (текущая просрочка)",
        "okved": "45.20",
        "tax_regime": "usn_15",
        "has_alfa_account": True,
        "owner_name": "Ковалёв Артём Сергеевич",
        "owner_age": 34,
        "assets": [],
    },
    {
        "id": "demo_disqualified",
        "inn": "0000701006",
        "legal_form": "ooo",
        "name": "ООО «Стройресурс», строительство (директор дисквалифицирован)",
        "okved": "41.20",
        "tax_regime": "osno",
        "has_alfa_account": True,
        "owner_name": "Белов Олег Николаевич",
        "owner_age": 47,
        "assets": [],
    },
    {
        "id": "demo_gray",
        "inn": "000080100400",
        "legal_form": "ip",
        "name": "ИП Зайцева О. И., продуктовый магазин (средний риск, без активов)",
        "okved": "47.11",
        "tax_regime": "usn_6",
        "has_alfa_account": True,
        "owner_name": "Зайцева Ольга Игоревна",
        "owner_age": 41,
        "assets": [],
    },
    {
        "id": "demo_gray_ooo",
        "inn": "0000901005",
        "legal_form": "ooo",
        "name": "ООО «Металлист», металлообработка (средний риск, есть оборудование)",
        "okved": "25.62",
        "tax_regime": "osno",
        "has_alfa_account": True,
        "owner_name": "Фролов Игорь Викторович",
        "owner_age": 50,
        "assets": [
            {"kind": "equipment", "description": "токарный станок с ЧПУ", "market_value": 4_000_000},
        ],
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
