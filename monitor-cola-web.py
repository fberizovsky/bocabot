#!/usr/bin/env python3
"""Dashboard web local para múltiples monitores de Queue-it."""

import argparse
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Queue-it Dashboard</title>
<style>
:root { color-scheme: dark; --bg:#0d1117; --card:#161b22; --line:#30363d; --text:#e6edf3; --muted:#8b949e; --blue:#58a6ff; --green:#3fb950; --yellow:#d29922; --red:#f85149; }
* { box-sizing:border-box; }
body { margin:0; background:radial-gradient(circle at top,#172236 0,#0d1117 42%); color:var(--text); font:14px system-ui,-apple-system,Segoe UI,sans-serif; }
main { max-width:1600px; margin:0 auto; padding:28px; }
header { display:flex; justify-content:space-between; align-items:end; gap:20px; margin-bottom:22px; }
h1 { margin:0 0 6px; font-size:clamp(24px,3vw,38px); letter-spacing:-1px; }
.subtitle { color:var(--muted); }
.clock { color:var(--muted); text-align:right; }
.summary { display:grid; grid-template-columns:repeat(4,minmax(130px,1fr)); gap:12px; margin-bottom:18px; }
.card { background:rgba(22,27,34,.88); border:1px solid var(--line); border-radius:12px; padding:16px 18px; box-shadow:0 10px 30px #0003; }
.label { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }
.value { font-size:28px; font-weight:700; margin-top:5px; }
.table-wrap { overflow:auto; background:rgba(22,27,34,.88); border:1px solid var(--line); border-radius:12px; box-shadow:0 10px 30px #0003; }
table { width:100%; border-collapse:collapse; min-width:900px; }
th { color:var(--muted); font-size:12px; text-align:left; text-transform:uppercase; letter-spacing:.06em; background:#1c2128; position:sticky; top:0; }
th,td { padding:12px 14px; border-bottom:1px solid var(--line); white-space:nowrap; }
tr:last-child td { border-bottom:0; }
td:first-child { color:var(--muted); width:45px; }
.status { display:inline-flex; align-items:center; gap:7px; font-weight:700; }
.status:before { content:""; width:8px; height:8px; border-radius:50%; background:var(--muted); }
.RUNNING { color:var(--green); }.RUNNING:before { background:var(--green); box-shadow:0 0 8px var(--green); }
.WAITING,.STARTING { color:var(--yellow); }.WAITING:before,.STARTING:before { background:var(--yellow); }
.ERROR { color:var(--red); }.ERROR:before { background:var(--red); }
.DONE { color:var(--blue); }.DONE:before { background:var(--blue); }
.queue { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; color:#b6d7ff; }
.muted { color:var(--muted); }
@media (max-width:700px) { main { padding:16px; } header { align-items:start; flex-direction:column; }.clock { text-align:left; }.summary { grid-template-columns:repeat(2,1fr); } }
</style>
</head>
<body>
<main>
<header><div><h1>Queue-it Dashboard</h1><div class="subtitle">Monitoreo local de múltiples colas</div></div><div class="clock" id="clock">Conectando...</div></header>
<section class="summary">
<div class="card"><div class="label">Total</div><div class="value" id="total">-</div></div>
<div class="card"><div class="label">Activos</div><div class="value" id="active">-</div></div>
<div class="card"><div class="label">Listos</div><div class="value" id="done">-</div></div>
<div class="card"><div class="label">Errores</div><div class="value" id="errors">-</div></div>
</section>
<div class="table-wrap"><table><thead><tr><th>#</th><th>Estado</th><th>Queue ID</th><th>Faltan</th><th>Hora estimada</th><th>Forecast</th><th>Actualizado</th><th>Detalle</th></tr></thead><tbody id="rows"></tbody></table></div>
</main>
<script>
const esc = value => String(value ?? "-").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function update() {
  try {
    const response = await fetch("/api/status", {cache:"no-store"});
    const data = await response.json();
    const counts = data.reduce((a, item) => { a[item.state] = (a[item.state] || 0) + 1; return a; }, {});
    total.textContent = data.length;
    active.textContent = (counts.RUNNING || 0) + (counts.WAITING || 0) + (counts.STARTING || 0);
    done.textContent = counts.DONE || 0;
    errors.textContent = counts.ERROR || 0;
    rows.innerHTML = data.map(item => `<tr><td>${item.index}</td><td><span class="status ${esc(item.state)}">${esc(item.state)}</span></td><td class="queue">${esc(item.queue_id)}</td><td>${esc(item.remaining)}</td><td>${esc(item.estimated)}</td><td>${esc(item.forecast)}</td><td class="muted">${esc(item.updated)}</td><td>${esc(item.message)}</td></tr>`).join("");
    clock.textContent = `Actualizado ${new Date().toLocaleTimeString()}`;
  } catch (error) { clock.textContent = "Esperando al servidor..."; }
}
update(); setInterval(update, 1000);
</script>
</body>
</html>"""


class Dashboard:
    def __init__(self, script_dir: Path, count: int, launch_delay: float):
        self.script_dir = script_dir
        self.count = count
        self.launch_delay = launch_delay
        self.work_dir = Path(tempfile.mkdtemp(prefix="monitor-cola-"))
        self.processes: list[subprocess.Popen[bytes]] = []

    def start(self) -> None:
        script = self.script_dir / "monitor-cola.sh"
        for index in range(1, self.count + 1):
            status_file = self.work_dir / f"status-{index}"
            log_file = self.work_dir / f"log-{index}"
            log = log_file.open("wb")
            process = subprocess.Popen(
                [str(script)],
                cwd=self.script_dir,
                env={**os.environ, "MONITOR_STATUS_FILE": str(status_file)},
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            self.processes.append(process)
            time.sleep(self.launch_delay)

    def status(self) -> list[dict[str, str | int]]:
        result = []
        for index in range(1, self.count + 1):
            values = ["STARTING", "-", "-", "-", "-", "-", "esperando inicio"]
            status_file = self.work_dir / f"status-{index}"
            try:
                values = status_file.read_text().rstrip("\n").split("\t")
            except FileNotFoundError:
                pass
            values += ["-"] * (7 - len(values))
            result.append({
                "index": index, "state": values[0], "queue_id": values[1],
                "remaining": values[2], "estimated": values[3], "forecast": values[4],
                "updated": values[5], "message": values[6],
            })
        return result

    def stop(self) -> None:
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
        for process in self.processes:
            process.wait()
        shutil.rmtree(self.work_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("count", nargs="?", type=int, default=int(os.getenv("MONITOR_COUNT", "100")))
    parser.add_argument("--port", type=int, default=int(os.getenv("MONITOR_WEB_PORT", "8765")))
    parser.add_argument("--launch-delay", type=float, default=float(os.getenv("MONITOR_LAUNCH_DELAY", "0.2")))
    args = parser.parse_args()
    if args.count < 1 or args.port < 1 or args.launch_delay < 0:
        parser.error("count, port y launch-delay deben ser valores válidos")

    dashboard = Dashboard(Path(__file__).resolve().parent, args.count, args.launch_delay)
    dashboard.start()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                body = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            elif self.path == "/api/status":
                body = json.dumps(dashboard.status()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
            else:
                self.send_error(404)
                return
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Dashboard web: http://127.0.0.1:{args.port}")
    print(f"Monitores activos: {args.count}. Presioná Ctrl+C para detenerlos.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        dashboard.stop()


if __name__ == "__main__":
    main()
