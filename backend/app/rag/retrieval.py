import math
import os
import re
from functools import lru_cache

from fastembed import SparseTextEmbedding
from langchain_ollama import OllamaEmbeddings
from qdrant_client import QdrantClient, models


QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "alfa_knowledge")

OLLAMA_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://host.docker.internal:11434",
)
EMBEDDING_MODEL = os.getenv(
    "OLLAMA_EMBEDDING_MODEL",
    "qwen3-embedding:0.6b",
)

BM25_MODEL = "Qdrant/bm25"

TOKEN_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)

STOP_WORDS = {
    "и", "в", "во", "на", "по", "для", "с", "со", "к", "ко",
    "о", "об", "от", "до", "из", "у", "а", "но", "или", "что",
    "как", "это", "мне", "мой", "можно", "ли",
}

QUERY_EXPANSIONS = {
    "ип": "индивидуальный предприниматель",
    "ооо": "юридическое лицо организация",
    "бки": "бюро кредитных историй кредитная история",
    "оборотка": "оборотный капитал оборотные средства",
    "кассовый разрыв": "овердрафт краткосрочное финансирование",
    "залог": "обеспечение имущество",
    "лизинг": "финансирование транспорта оборудования",
}


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=QDRANT_URL,
        timeout=30,
    )


@lru_cache(maxsize=1)
def get_dense_model() -> OllamaEmbeddings:
    return OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_URL,
    )


@lru_cache(maxsize=1)
def get_sparse_model() -> SparseTextEmbedding:
    return SparseTextEmbedding(model_name=BM25_MODEL)


def tokenize(text: str) -> set[str]:
    return {
        token.lower()
        for token in TOKEN_RE.findall(text)
        if len(token) > 1 and token.lower() not in STOP_WORDS
    }


def expand_query(query: str) -> str:
    additions = [
        expansion
        for phrase, expansion in QUERY_EXPANSIONS.items()
        if phrase in query.lower()
    ]

    if not additions:
        return query

    return f"{query} {' '.join(additions)}"


def overlap_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0

    return len(left & right) / math.sqrt(len(left) * len(right))


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0

    return len(left & right) / len(left | right)


def rerank_and_diversify(query: str, points, top_k: int) -> list[dict]:
    query_tokens = tokenize(query)
    candidates = []

    total = max(len(points), 1)

    for rank, point in enumerate(points):
        payload = point.payload or {}

        text = payload.get("text", "")
        title = payload.get("title", "")
        url = payload.get("url", "")

        text_tokens = tokenize(text)
        title_tokens = tokenize(title)

        rank_score = 1 - rank / total
        text_overlap = overlap_score(query_tokens, text_tokens)
        title_overlap = overlap_score(query_tokens, title_tokens)

        exact_phrase = (
            1.0
            if query.lower() in f"{title}\n{text}".lower()
            else 0.0
        )

        relevance = (
            0.55 * rank_score
            + 0.25 * text_overlap
            + 0.15 * title_overlap
            + 0.05 * exact_phrase
        )

        candidates.append({
            "id": str(point.id),
            "score": relevance,
            "rrf_score": float(point.score or 0),
            "text": text,
            "title": title,
            "url": url,
            "kind": payload.get("kind", ""),
            "web_id": payload.get("web_id", ""),
            "chunk_index": payload.get("chunk_index"),
            "_tokens": text_tokens,
        })

    selected = []
    used_urls: dict[str, int] = {}

    while candidates and len(selected) < top_k:
        best = None
        best_adjusted_score = float("-inf")

        for candidate in candidates:
            similarity_penalty = max(
                (
                    jaccard(
                        candidate["_tokens"],
                        chosen["_tokens"],
                    )
                    for chosen in selected
                ),
                default=0.0,
            )

            same_source_penalty = (
                0.08
                if candidate["url"]
                and used_urls.get(candidate["url"], 0) >= 1
                else 0.0
            )

            adjusted_score = (
                candidate["score"]
                - 0.20 * similarity_penalty
                - same_source_penalty
            )

            if adjusted_score > best_adjusted_score:
                best = candidate
                best_adjusted_score = adjusted_score

        candidates.remove(best)
        best["score"] = round(best_adjusted_score, 4)
        selected.append(best)

        if best["url"]:
            used_urls[best["url"]] = (
                used_urls.get(best["url"], 0) + 1
            )

    result = []

    for item in selected:
        item = dict(item)
        item.pop("_tokens", None)
        item["rrf_score"] = round(item["rrf_score"], 6)
        result.append(item)

    return result


def hybrid_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Dense + BM25 retrieval, RRF fusion and local reranking.

    Возвращает разнообразные фрагменты с URL и заголовками,
    пригодные для формирования ответа с источниками.
    """
    query = query.strip()

    if not query:
        return []

    if not 1 <= top_k <= 10:
        raise ValueError("top_k должен находиться в диапазоне 1..10")

    expanded_query = expand_query(query)

    dense_vector = get_dense_model().embed_query(expanded_query)

    sparse_embedding = next(
        iter(
            get_sparse_model().query_embed(
                expanded_query
            )
        )
    )

    sparse_vector = models.SparseVector(
        indices=sparse_embedding.indices.tolist(),
        values=sparse_embedding.values.tolist(),
    )

    candidate_limit = max(30, top_k * 8)

    response = get_qdrant_client().query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            models.Prefetch(
                query=dense_vector,
                using="dense",
                limit=candidate_limit,
            ),
            models.Prefetch(
                query=sparse_vector,
                using="bm25",
                limit=candidate_limit,
            ),
        ],
        query=models.FusionQuery(
            fusion=models.Fusion.RRF,
        ),
        limit=candidate_limit,
        with_payload=True,
    )

    return rerank_and_diversify(
        query=query,
        points=response.points,
        top_k=top_k,
    )