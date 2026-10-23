
import argparse
import json
import os
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


@lru_cache(maxsize=1)
def get_qdrant_client():
    return QdrantClient(url=QDRANT_URL, timeout=120)


@lru_cache(maxsize=1)
def get_dense_model():
    return OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_URL,
    )


@lru_cache(maxsize=1)
def get_sparse_model():
    return SparseTextEmbedding(model_name=BM25_MODEL)


def hybrid_search(query: str, top_k: int = 5) -> list[dict]:
    """Гибридный поиск по Qdrant с RRF."""

    query = query.strip()

    if not query:
        return []

    if top_k < 1:
        raise ValueError("top_k должен быть >= 1")

    dense_vector = get_dense_model().embed_query(query)

    sparse_embedding = next(
        iter(get_sparse_model().query_embed(query))
    )

    sparse_vector = models.SparseVector(
        indices=sparse_embedding.indices.tolist(),
        values=sparse_embedding.values.tolist(),
    )

    candidate_limit = max(20, top_k * 4)

    results = get_qdrant_client().query_points(
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
        limit=top_k,
        with_payload=True,
    )

    documents = []

    for point in results.points:
        payload = point.payload or {}

        documents.append({
            "id": str(point.id),
            "score": point.score,
            "text": payload.get("text", ""),
            "title": payload.get("title", ""),
            "url": payload.get("url", ""),
            "kind": payload.get("kind", ""),
            "web_id": payload.get("web_id", ""),
            "chunk_index": payload.get("chunk_index"),
        })

    return documents


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--query",
        required=True,
        help="Поисковый запрос",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )

    args = parser.parse_args()

    results = hybrid_search(query=args.query, top_k=args.top_k)

    print(json.dumps(results, ensure_ascii=False, indent=2))
