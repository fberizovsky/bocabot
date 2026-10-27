#!/usr/bin/env python3
"""Obtiene un queueId y monitorea el tiempo restante de una fila Queue-it."""

import json
import os
import time
import uuid
from datetime import datetime
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


LOGIN_URL = os.getenv(
    "BOCA_LOGIN_URL", "https://bocasocios.bocajuniors.com.ar/auth/login"
)
QUEUE_HOST = os.getenv("QUEUE_HOST", "https://bocajuniors.queue-it.net")
CUSTOMER = os.getenv("QUEUE_CUSTOMER", "bocajuniors")
EVENT_ID = os.getenv("QUEUE_EVENT", "e20261016adh")
QUEUE_LABEL = os.getenv("QUEUE_LABEL", "Boca Socios")
REDIRECT_TARGET = os.getenv(
    "QUEUE_TARGET", "https://bocasocios-gw.bocajuniors.com.ar/queueit/redirect"
)
DEFAULT_INTERVAL_MS = int(os.getenv("POLL_INTERVAL_MS", "40000"))


def read_json(opener, request):
    """Envía una petición, valida el estado HTTP y devuelve su JSON."""
    try:
        with opener.open(request) as response:
            body = response.read().decode("utf-8")
    except (HTTPError, URLError) as error:
        raise RuntimeError(f"Error HTTP: {error}") from error

    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"La respuesta no es JSON: {body[:500]}") from error


def print_status(status):
    ticket = status.get("ticket") or {}
    now = datetime.now().astimezone().strftime("%H:%M:%S")
    print(
        f"[{now}] faltan: {ticket.get('whichIsIn', 'sin dato')} | "
        f"hora estimada: {ticket.get('expectedServiceTime', 'sin dato')} | "
        f"actualizado: {ticket.get('lastUpdated', 'sin dato')} | "
        f"estado: {status.get('forecastStatus', 'sin dato')}",
        flush=True,
    )


def main():
    # Paso 1: crear una sesión HTTP que conserva cookies en memoria.
    cookies = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookies))

    # Paso 2: obtener las cookies iniciales sin abrir un navegador.
    with opener.open(Request(LOGIN_URL, method="GET")) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"No se pudo abrir la página inicial: {response.status}")

    common_headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{QUEUE_HOST}/",
    }

    # Paso 3: pedir un lugar en la cola y obtener el queueId.
    enqueue_url = (
        f"{QUEUE_HOST}/spa-api/queue/{CUSTOMER}/{EVENT_ID}/enqueue?"
        + urlencode({"cid": "es-ES", "l": QUEUE_LABEL, "t": REDIRECT_TARGET})
    )
    enqueue = read_json(
        opener,
        Request(
            enqueue_url,
            data=b"{}",
            headers=common_headers,
            method="POST",
        ),
    )
    queue_id = enqueue.get("queueId")
    if not queue_id:
        raise RuntimeError(f"La respuesta enqueue no contiene queueId: {enqueue}")

    # Paso 4: construir la URL de estado con un identificador de sesión nuevo.
    status_url = (
        f"{QUEUE_HOST}/spa-api/queue/{CUSTOMER}/{EVENT_ID}/{queue_id}/status?"
        + urlencode(
            {
                "cid": "es-ES",
                "l": QUEUE_LABEL,
                "t": REDIRECT_TARGET,
                "seid": str(uuid.uuid4()),
                "sets": str(int(time.time() * 1000)),
            }
        )
    )
    print(f"queueId: {queue_id}")
    print(f"Consultando: {QUEUE_HOST}/spa-api/queue/{CUSTOMER}/{EVENT_ID}/{queue_id}/status")

    # Paso 5: consultar status hasta que Queue-it indique que se puede continuar.
    interval_ms = DEFAULT_INTERVAL_MS
    while True:
        status = read_json(
            opener,
            Request(
                status_url,
                data=b"{}",
                headers=common_headers,
                method="POST",
            ),
        )
        print_status(status)
        if status.get("redirectUrl") or status.get("forecastStatus") == "Redirect":
            print("La cola indicó que ya se puede continuar.")
            return

        interval_ms = int(status.get("updateInterval") or interval_ms)
        time.sleep(interval_ms / 1000)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitor detenido.")
    except (RuntimeError, ValueError) as error:
        print(f"Error monitoreando la cola: {error}")
        raise SystemExit(1)
