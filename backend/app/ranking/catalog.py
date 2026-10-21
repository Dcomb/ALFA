import json
from functools import lru_cache
from pathlib import Path

CATALOG_PATH = Path(__file__).parent / 'data' / 'alfa_sme_products.json'


@lru_cache
def load_catalog(path=CATALOG_PATH):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def products():
    return load_catalog()['products']


def get_product(product_id):
    for p in products():
        if p['id'] == product_id:
            return p
    raise KeyError(product_id)


def common_requirements():
    return load_catalog()['common_requirements']
