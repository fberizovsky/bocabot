#!/usr/bin/env bash
set -euo pipefail

# Monitor de Queue-it usando solamente curl y jq.
LOGIN_URL="${BOCA_LOGIN_URL:-https://bocasocios.bocajuniors.com.ar/auth/login}"
QUEUE_HOST="${QUEUE_HOST:-https://bocajuniors.queue-it.net}"
CUSTOMER="${QUEUE_CUSTOMER:-bocajuniors}"
EVENT_ID="${QUEUE_EVENT:-e20261107adh}"
QUEUE_LABEL="${QUEUE_LABEL:-Boca Socios}"
REDIRECT_TARGET="${QUEUE_TARGET:-https://bocasocios-gw.bocajuniors.com.ar/queueit/redirect}"
DEFAULT_INTERVAL_MS="${POLL_INTERVAL_MS:-40000}"
STATUS_FILE="${MONITOR_STATUS_FILE:-}"

write_status() {
  [[ -n "$STATUS_FILE" ]] || return 0
  local state="$1"
  local queue_id="${2:-}"
  local remaining="${3:-}"
  local estimated="${4:-}"
  local forecast="${5:-}"
  local message="${6:-}"
  local temporary_file="${STATUS_FILE}.tmp"

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$state" "$queue_id" "$remaining" "$estimated" "$forecast" \
    "$(date +%H:%M:%S)" "$message" >"$temporary_file"
  mv "$temporary_file" "$STATUS_FILE"
}

on_exit() {
  local exit_code=$?
  if ((exit_code != 0)); then
    write_status "ERROR" "" "" "" "" "proceso finalizado con error ($exit_code)"
  fi
  rm -f "$COOKIE_FILE"
  exit "$exit_code"
}

command -v curl >/dev/null || { echo "Error: falta curl." >&2; exit 1; }
command -v jq >/dev/null || { echo "Error: falta jq." >&2; exit 1; }

COOKIE_FILE="$(mktemp)"
trap on_exit EXIT
write_status "STARTING" "" "" "" "" "iniciando"

LABEL_ENCODED="$(jq -rn --arg value "$QUEUE_LABEL" '$value | @uri')"
TARGET_ENCODED="$(jq -rn --arg value "$REDIRECT_TARGET" '$value | @uri')"

# Paso 1: obtener cookies iniciales; se guardan solo en un archivo temporal.
curl --fail-with-body --silent --show-error \
  --cookie-jar "$COOKIE_FILE" \
  "$LOGIN_URL" >/dev/null

ENQUEUE_URL="$QUEUE_HOST/spa-api/queue/$CUSTOMER/$EVENT_ID/enqueue?cid=es-ES&l=$LABEL_ENCODED&t=$TARGET_ENCODED"

# Paso 2: pedir un lugar en la cola y extraer queueId con jq.
ENQUEUE="$(
  curl --fail-with-body --silent --show-error \
    --cookie "$COOKIE_FILE" --cookie-jar "$COOKIE_FILE" \
    -X POST "$ENQUEUE_URL" \
    -H 'Accept: application/json, text/javascript, */*; q=0.01' \
    -H 'Content-Type: application/json' \
    -H 'X-Requested-With: XMLHttpRequest' \
    -H "Referer: $QUEUE_HOST/" \
    --data '{}'
)"
QUEUE_ID="$(jq -er '.queueId // empty' <<<"$ENQUEUE")" || {
  echo "Error: enqueue no devolvió queueId: $ENQUEUE" >&2
  exit 1
}
write_status "WAITING" "$QUEUE_ID" "" "" "" "queueId obtenido"

# Paso 3: generar seid y sets, como hace el navegador.
if command -v uuidgen >/dev/null; then
  SEID="$(uuidgen)"
else
  SEID="$(cat /proc/sys/kernel/random/uuid)"
fi
SETS="$(date +%s%3N)"
STATUS_URL="$QUEUE_HOST/spa-api/queue/$CUSTOMER/$EVENT_ID/$QUEUE_ID/status?cid=es-ES&l=$LABEL_ENCODED&t=$TARGET_ENCODED&seid=$SEID&sets=$SETS"

echo "queueId: $QUEUE_ID"
echo "Consultando: $QUEUE_HOST/spa-api/queue/$CUSTOMER/$EVENT_ID/$QUEUE_ID/status"

# Paso 4: consultar status y mostrar ticket.whichIsIn hasta finalizar.
INTERVAL_MS="$DEFAULT_INTERVAL_MS"
while true; do
  STATUS="$(
    curl --fail-with-body --silent --show-error \
      --cookie "$COOKIE_FILE" --cookie-jar "$COOKIE_FILE" \
      -X POST "$STATUS_URL" \
      -H 'Accept: application/json, text/javascript, */*; q=0.01' \
      -H 'Content-Type: application/json' \
      -H 'X-Requested-With: XMLHttpRequest' \
      -H "Referer: $QUEUE_HOST/" \
      --data '{}'
  )"

  REMAINING="$(jq -r '.ticket.whichIsIn // "sin dato"' <<<"$STATUS")"
  ESTIMATED="$(jq -r '.ticket.expectedServiceTime // "sin dato"' <<<"$STATUS")"
  FORECAST="$(jq -r '.forecastStatus // "sin dato"' <<<"$STATUS")"
  write_status "RUNNING" "$QUEUE_ID" "$REMAINING" "$ESTIMATED" "$FORECAST" "consultando"
  printf '[%s] faltan: %s | hora estimada: %s | actualizado: %s | estado: %s\n' \
    "$(date +%H:%M:%S)" "$REMAINING" "$ESTIMATED" \
    "$(jq -r '.ticket.lastUpdated // "sin dato"' <<<"$STATUS")" "$FORECAST"

  if jq -e '.redirectUrl or .forecastStatus == "Redirect"' <<<"$STATUS" >/dev/null; then
    write_status "DONE" "$QUEUE_ID" "$REMAINING" "$ESTIMATED" "$FORECAST" "la cola indicó que ya se puede continuar"
    echo "La cola indicó que ya se puede continuar."
    break
  fi

  INTERVAL_MS="$(jq -r --arg fallback "$INTERVAL_MS" '.updateInterval // ($fallback | tonumber)' <<<"$STATUS")"
  # LC_NUMERIC=C evita que awk use coma decimal en configuraciones regionales como es_AR.
  sleep "$(LC_NUMERIC=C awk -v milliseconds="$INTERVAL_MS" 'BEGIN { printf "%.3f", milliseconds / 1000 }')"
done