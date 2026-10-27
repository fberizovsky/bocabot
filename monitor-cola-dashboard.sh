#!/usr/bin/env bash
set -u

COUNT="${1:-${MONITOR_COUNT:-100}}"
LAUNCH_DELAY="${MONITOR_LAUNCH_DELAY:-0.2}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$(mktemp -d)"
declare -a PIDS=()

cleanup() {
  local pid
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  for pid in "${PIDS[@]}"; do
    wait "$pid" 2>/dev/null || true
  done
  rm -rf "$WORK_DIR"
  printf '\nMonitores detenidos.\n'
}
trap cleanup INT TERM EXIT

if ! [[ "$COUNT" =~ ^[1-9][0-9]*$ ]]; then
  printf 'Error: la cantidad debe ser un entero positivo.\n' >&2
  exit 2
fi

command -v curl >/dev/null || { echo "Error: falta curl." >&2; exit 2; }
command -v jq >/dev/null || { echo "Error: falta jq." >&2; exit 2; }

for ((index = 1; index <= COUNT; index++)); do
  status_file="$WORK_DIR/status-$index"
  log_file="$WORK_DIR/log-$index"
  MONITOR_STATUS_FILE="$status_file" \
    "$SCRIPT_DIR/monitor-cola.sh" >"$log_file" 2>&1 &
  PIDS[index - 1]=$!
  sleep "$LAUNCH_DELAY"
done

printf '\033[2J\033[H'
while true; do
  printf '\033[H'
  printf 'Dashboard Queue-it | %d monitores | Ctrl+C para detener | %s\n\n' \
    "$COUNT" "$(date '+%Y-%m-%d %H:%M:%S')"
  printf '%-5s %-10s %-38s %-18s %-14s %-10s %s\n' \
    '#' 'estado' 'queueId' 'faltan' 'hora estimada' 'forecast' 'detalle'
  printf '%s\n' '----- ---------- -------------------------------------- ------------------ -------------- ---------- ------------------------------'

  for ((index = 1; index <= COUNT; index++)); do
    status_file="$WORK_DIR/status-$index"
    if [[ -f "$status_file" ]]; then
      IFS=$'\t' read -r state queue_id remaining estimated forecast updated message \
        <"$status_file"
    else
      state="STARTING"
      queue_id="-" remaining="-" estimated="-" forecast="-" updated="-" message="esperando inicio"
    fi
    printf '%-5s %-10.10s %-38.38s %-18.18s %-14.14s %-10.10s %s\n' \
      "$index" "$state" "${queue_id:--}" "${remaining:--}" "${estimated:--}" \
      "${forecast:--}" "${message:--}"
  done
  sleep 1
done
