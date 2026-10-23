import hashlib
import html
import json
import re
from pathlib import Path

import pandas as pd
from langchain_text_splitters import RecursiveCharacterTextSplitter


RAW_PATH = Path("/app/data/raw/websites_updated.csv")
OUTPUT_PATH = Path("/app/data/processed/websites_chunks.jsonl")

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
MIN_CHUNK_LENGTH = 50
MIN_DOCUMENT_LENGTH = 50


# Удаляем только явно служебные строки.
# Список можно расширять после анализа данных.
BOILERPLATE_PATTERNS = [
    r"^Принять все cookie$",
    r"^Настройки cookie$",
    r"^Отклонить cookie$",
    r"^Политика использования файлов cookie$",
    r"^Вернуться наверх$",
    r"^Наверх$",
]


def clean_text(text: str) -> str:
    """Базовая очистка текста без удаления полезного содержания."""

    text = html.unescape(str(text))

    # Удаление HTML-тегов, если CSV содержит HTML-разметку
    text = re.sub(r"<[^>]+>", " ", text)

    # Нормализация пробелов
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)

    # Удаление управляющих символов
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)

    # Очистка служебных строк
    cleaned_lines = []

    for line in text.splitlines():
        line = line.strip()

        if not line:
            cleaned_lines.append("")
            continue

        if any(
            re.fullmatch(pattern, line, flags=re.IGNORECASE)
            for pattern in BOILERPLATE_PATTERNS
        ):
            continue

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # Удаление избыточных переносов строк
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def get_chunk_id(
    web_id: str,
    chunk_index: int,
    text: str,
) -> str:
    """Стабильный SHA-256 идентификатор."""

    value = f"{web_id}:{chunk_index}:{text}"

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def preprocess():
    print("Загрузка исходных данных...")

    df = pd.read_csv(
        RAW_PATH,
        dtype={"web_id": str},
    )

    initial_count = len(df)
    print(f"Исходных документов: {initial_count}")

    # Проверяем структуру CSV
    required_columns = {
        "web_id",
        "url",
        "kind",
        "title",
        "text",
    }

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Отсутствуют столбцы: {missing_columns}"
        )

    # Убираем записи без URL и текста
    df = df.dropna(
        subset=["url", "text"]
    ).copy()

    # Очистка
    df["text"] = df["text"].apply(clean_text)
    df["title"] = df["title"].fillna("").apply(clean_text)
    df["kind"] = df["kind"].fillna("unknown")

    # Короткие документы
    df = df[
        df["text"].str.len() >= MIN_DOCUMENT_LENGTH
    ].copy()

    # Дедупликация
    before_dedup = len(df)

    df = df.drop_duplicates(subset=["url"])
    df = df.drop_duplicates(subset=["text"])

    duplicates_removed = before_dedup - len(df)

    print(f"Удалено дубликатов: {duplicates_removed}")
    print(f"Документов после очистки: {len(df)}")

    # Разделение документов
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    total_chunks = 0
    short_chunks_removed = 0

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:

        for row in df.itertuples(index=False):

            chunks = splitter.split_text(row.text)

            for index, chunk in enumerate(chunks):

                chunk = chunk.strip()

                # Не индексируем короткие чанки
                if len(chunk) < MIN_CHUNK_LENGTH:
                    short_chunks_removed += 1
                    continue

                chunk_id = get_chunk_id(
                    row.web_id,
                    index,
                    chunk,
                )

                record = {
                    "id": chunk_id,
                    "text": chunk,
                    "metadata": {
                        "web_id": row.web_id,
                        "url": row.url,
                        "title": row.title,
                        "kind": str(row.kind),
                        "chunk_index": index,
                    },
                }

                file.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                    ) + "\n"
                )

                total_chunks += 1

    print(f"Исходных документов: {initial_count}")
    print(f"Документов после очистки: {len(df)}")
    print(f"Удалено дубликатов: {duplicates_removed}")
    print(f"Удалено коротких чанков: {short_chunks_removed}")
    print(f"Итоговое количество чанков: {total_chunks}")
    print(f"Результат: {OUTPUT_PATH}")


if __name__ == "__main__":
    preprocess()