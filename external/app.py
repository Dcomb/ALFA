import json
import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException

DATA_PATH = Path(os.getenv("EXTERNAL_DATA", Path(__file__).parent / "data" / "world.json"))
SLOW_SECONDS = float(os.getenv("SLOW_SECONDS", "1"))
HANG_SECONDS = float(os.getenv("HANG_SECONDS", "10"))

WORLD = json.loads(DATA_PATH.read_text(encoding="utf-8"))

app = FastAPI(
    title="Внешние источники (мок)",
    description="ЕГРЮЛ/ЕГРИП, ФНС «Прозрачный бизнес», ГИР БО, обороты по счёту, БКИ",
)


def answer(source, inn):
    company = WORLD.get(inn)

    if company is None:
        raise HTTPException(404, "ИНН не найден")

    behavior = company.get("behavior", {}).get(source)

    if behavior == "error":
        raise HTTPException(503, "источник временно недоступен")
    if behavior == "slow":
        time.sleep(SLOW_SECONDS)
    if behavior == "hang":
        time.sleep(HANG_SECONDS)

    data = company.get(source)

    if data is None:
        raise HTTPException(404, "нет данных")

    return data


@app.get("/egrul/{inn}")
def egrul(inn: str):
    return answer("egrul", inn)


@app.get("/fns/{inn}")
def fns(inn: str):
    return answer("fns", inn)


@app.get("/girbo/{inn}")
def girbo(inn: str):
    return answer("girbo", inn)


@app.get("/bank/{inn}")
def bank(inn: str):
    return answer("bank", inn)


@app.get("/bki/{inn}")
def bki(inn: str):
    return answer("bki", inn)
