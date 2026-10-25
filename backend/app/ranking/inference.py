from .clients import get_client
from .engine import recommend
from .schemas import Need


def recommend_for_client(client_id, purpose=None, amount=None, term_months=None, top_k=3):
    client = get_client(client_id)
    if client is None:
        raise KeyError(client_id)
    need = Need(purpose=purpose, amount=amount, term_months=term_months)
    return recommend(client, need, top_k).model_dump()
