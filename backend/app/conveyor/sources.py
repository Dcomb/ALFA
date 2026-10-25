import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

SOURCES = ("egrul", "fns", "girbo", "bank", "bki")
FAILED = {"error", "timeout"}

TIMEOUT = float(os.getenv("EXTERNAL_TIMEOUT", "2"))
RETRIES = int(os.getenv("EXTERNAL_RETRIES", "2"))
BACKOFF = 0.3

transport = None

log = logging.getLogger("conveyor.sources")


def base_url():
    return os.getenv("EXTERNAL_API_URL", "http://external:8100")


def request(source, inn):
    with httpx.Client(base_url=base_url(), timeout=TIMEOUT, transport=transport) as client:
        return client.get(f"/{source}/{inn}")


def fetch(source, inn, application_id=None):
    started = time.monotonic()
    status, payload = "error", None

    for attempt in range(RETRIES + 1):
        try:
            response = request(source, inn)
            if response.status_code == 200:
                status, payload = "ok", response.json()
                break
            if response.status_code == 404:
                status = "not_found"
                break
            status = "error"
        except httpx.TimeoutException:
            status = "timeout"
        except httpx.HTTPError:
            status = "error"

        if attempt < RETRIES:
            time.sleep(BACKOFF * (attempt + 1))

    duration_ms = int((time.monotonic() - started) * 1000)
    log.info(
        "application=%s step=checking source=%s status=%s attempts=%s duration_ms=%s",
        application_id, source, status, attempt + 1, duration_ms,
    )

    return {"source": source, "status": status, "payload": payload, "duration_ms": duration_ms}


def fetch_all(inn, sources, application_id=None):
    if not sources:
        return []

    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        return list(pool.map(lambda source: fetch(source, inn, application_id), sources))
