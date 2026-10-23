
import argparse
import json
import os
import time
import uuid
from pathlib import Path

from fastembed import SparseTextEmbedding
from langchain_ollama import OllamaEmbeddings
from qdrant_client import QdrantClient, models


DATA_PATH = Path("/app/data/processed/websites_chunks.jsonl")

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


def load_chunks(limit=None):
    """Читаем подготовленные документы из JSONL."""
    chunks = []

    with DATA_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            record = json.loads(line)

            if not record.get("text", "").strip():
                continue

            chunks.append(record)

            if limit is not None and len(chunks) >= limit:
                break

    return chunks


def stable_uuid(chunk_id):
    """Преобразуем исходный SHA256 ID в стабильный UUID."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, str(chunk_id)))


def create_collection_if_missing(client, vector_size):
    """Создаём коллекцию для dense и sparse векторов."""

    if client.collection_exists(COLLECTION_NAME):
        info = client.get_collection(COLLECTION_NAME)

        vectors = info.config.params.vectors
        sparse_vectors = info.config.params.sparse_vectors or {}

        if (
            not isinstance(vectors, dict)
            or "dense" not in vectors
            or "bm25" not in sparse_vectors
            or vectors["dense"].size != vector_size
        ):
            raise ValueError(
                "Существующая коллекция имеет несовместимую "
                "схему. Проверь конфигурацию Qdrant."
            )

        print(f"Коллекция {COLLECTION_NAME} уже существует.")
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        },
        sparse_vectors_config={
            "bm25": models.SparseVectorParams(
                modifier=models.Modifier.IDF,
            ),
        },
    )

    print(f"Создана коллекция: {COLLECTION_NAME}")


def upload_batch(client, dense_model, sparse_model, batch):
    """Создаём векторы и загружаем один пакет."""

    texts = [record["text"] for record in batch]

    dense_vectors = dense_model.embed_documents(texts)
    sparse_vectors = list(sparse_model.embed(texts))

    points = []

    for record, dense, sparse in zip(
        batch,
        dense_vectors,
        sparse_vectors,
    ):
        point = models.PointStruct(
            id=stable_uuid(record["id"]),
            vector={
                "dense": dense,
                "bm25": models.SparseVector(
                    indices=sparse.indices.tolist(),
                    values=sparse.values.tolist(),
                ),
            },
            payload={
                "text": record["text"],
                **record.get("metadata", {}),
            },
        )

        points.append(point)

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
        wait=True,
    )


def ingest(limit=None, batch_size=16, retries=3):
    start_time = time.perf_counter()

    print("=== ALFA RAG INGESTION ===")

    chunks = load_chunks(limit=limit)

    print(f"Чанков для обработки: {len(chunks)}")

    if not chunks:
        print("Нет данных для загрузки.")
        return

    client = QdrantClient(
        url=QDRANT_URL,
        timeout=120,
    )

    dense_model = OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_URL,
    )

    print("Подключение к Ollama...")

    # Размерность получаем от самой модели
    test_vector = dense_model.embed_query(
        "Проверка модели эмбеддингов"
    )

    vector_size = len(test_vector)

    print(f"Dense model: {EMBEDDING_MODEL}")
    print(f"Vector size: {vector_size}")

    create_collection_if_missing(client, vector_size)

    print("Загрузка модели BM25...")

    sparse_model = SparseTextEmbedding(
        model_name=BM25_MODEL,
    )

    processed = 0
    skipped = 0

    total = len(chunks)

    for offset in range(0, total, batch_size):
        batch = chunks[offset:offset + batch_size]

        ids = [stable_uuid(record["id"]) for record in batch]

        # Не пересчитываем уже загруженные точки
        existing = client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=ids,
            with_payload=False,
            with_vectors=False,
        )

        existing_ids = {str(point.id) for point in existing}

        pending = [
            record
            for record in batch
            if stable_uuid(record["id"]) not in existing_ids
        ]

        skipped += len(batch) - len(pending)

        if pending:
            for attempt in range(1, retries + 1):
                try:
                    upload_batch(
                        client,
                        dense_model,
                        sparse_model,
                        pending,
                    )

                    processed += len(pending)
                    break

                except Exception as exc:
                    print(
                        f"Ошибка пакета {offset}: {exc}"
                    )

                    if attempt == retries:
                        raise

                    time.sleep(min(2 ** attempt, 10))

        completed = min(offset + batch_size, total)

        print(
            f"\rПрогресс: {completed}/{total} | "
            f"Новых: {processed} | "
            f"Пропущено: {skipped}",
            end="",
            flush=True,
        )

    elapsed = time.perf_counter() - start_time

    print("\n\n=== INGESTION COMPLETE ===")
    print(f"Новых чанков: {processed}")
    print(f"Уже существовали: {skipped}")
    print(f"Время: {elapsed:.1f} сек.")

    info = client.get_collection(COLLECTION_NAME)

    print(f"Коллекция: {COLLECTION_NAME}")
    print(f"Точек в Qdrant: {info.points_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Максимальное число чанков",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="Размер пакета",
    )

    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        parser.error("--limit должен быть положительным")

    if args.batch_size <= 0:
        parser.error("--batch-size должен быть положительным")

    ingest(limit=args.limit, batch_size=args.batch_size)
