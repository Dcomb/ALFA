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
            {"kind": "real_estate", "description": "складское помещение 600 м²", "market_value": 20000000},
            {"kind": "vehicle", "description": "седельный тягач, 2021 г.", "market_value": 7500000},
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
            {"kind": "equipment", "description": "токарный станок с ЧПУ", "market_value": 4000000},
        ],
    },
]

DEMO_REGISTRATION_META = {
    "demo_cafe": {"ogrn": "324770000101950", "registration_date": "15.01.2024", "phone": "+7 987 234 67 82"},
    "demo_logistics": {"ogrn": "1227700201003", "registration_date": "11.10.2022", "phone": "+7 905 455 24 10"},
    "demo_newbie": {"ogrn": "326770030100210", "registration_date": "18.05.2026", "phone": "+7 916 300 10 21"},
    "demo_unstable_bki": {"ogrn": "323770040100499", "registration_date": "01.03.2023", "phone": "+7 916 400 10 49"},
    "demo_liquidated": {"ogrn": "1197700501007", "registration_date": "17.06.2019", "phone": "+7 905 500 10 07"},
    "demo_overdue": {"ogrn": "319770060100440", "registration_date": "17.06.2019", "phone": "+7 916 600 10 44"},
    "demo_disqualified": {"ogrn": "1217700701006", "registration_date": "01.09.2021", "phone": "+7 905 700 10 06"},
    "demo_gray": {"ogrn": "323770080100400", "registration_date": "10.04.2023", "phone": "+7 916 800 10 40"},
    "demo_gray_ooo": {"ogrn": "1237700901005", "registration_date": "10.04.2023", "phone": "+7 905 900 10 05"},
}


def seed_demo_clients(session):
    for data in DEMO_CLIENTS:
        metadata = DEMO_REGISTRATION_META[data["id"]]
        existing = session.get(Client, data["id"])
        if existing is not None:
            for key, value in metadata.items():
                setattr(existing, key, value)
            continue
        fields = {key: value for key, value in data.items() if key != "assets"}
        client = Client(**fields, **metadata, assets=[Asset(**asset) for asset in data["assets"]])
        session.add(client)
    session.commit()
