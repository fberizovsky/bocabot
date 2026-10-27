# Dashboard web de monitores de cola

## Requisitos

- Python 3.9 o superior.
- Bash.
- `curl`.
- `jq`.
- Conexión a Internet.

En Ubuntu o Debian:

```bash
sudo apt update
sudo apt install curl jq
```

## Ejecución

Dar permisos de ejecución una sola vez:

```bash
chmod +x monitor-cola-web.sh monitor-cola.sh
```

Iniciar 100 monitores y abrir el dashboard en
[http://127.0.0.1:8765](http://127.0.0.1:8765):

```bash
./monitor-cola-web.sh
```

La cantidad de monitores se puede indicar como primer argumento:

```bash
./monitor-cola-web.sh 20
```

También se puede cambiar el puerto:

```bash
./monitor-cola-web.sh 100 --port 9000
```

Para detener el servidor y todos los monitores, presionar `Ctrl+C`.

## Configuración

Se pueden sobrescribir los valores predeterminados con variables de entorno:

| Variable | Valor predeterminado | Uso |
| --- | --- | --- |
| `BOCA_LOGIN_URL` | `https://bocasocios.bocajuniors.com.ar/auth/login` | Página inicial |
| `QUEUE_HOST` | `https://bocajuniors.queue-it.net` | Servidor de Queue-it |
| `QUEUE_CUSTOMER` | `bocajuniors` | Cliente de Queue-it |
| `QUEUE_EVENT` | `e20261101adh` | Evento de la fila |
| `QUEUE_LABEL` | `Boca Socios` | Etiqueta enviada a Queue-it |
| `QUEUE_TARGET` | `https://bocasocios-gw.bocajuniors.com.ar/queueit/redirect` | URL de retorno |
| `POLL_INTERVAL_MS` | El intervalo indicado por el servidor, normalmente 40000 ms | Intervalo mínimo entre consultas |
| `MONITOR_COUNT` | `100` | Cantidad predeterminada de monitores |
| `MONITOR_LAUNCH_DELAY` | `0.2` | Demora entre lanzamientos |
| `MONITOR_WEB_PORT` | `8765` | Puerto del dashboard web |

Ejemplo:

```bash
QUEUE_EVENT=otro_evento MONITOR_COUNT=20 ./monitor-cola-web.sh
```

El `QUEUE_EVENT` debe ser el identificador real de la campaña de Queue-it.
Puede obtenerse observando las peticiones de red del sitio cuando se publique
o active la fila.

El tablero incluye una columna **Link** para cada `queueId`. El enlace se
genera con el formato de Queue-it y el botón **Copiar** permite copiarlo:

```text
https://bocajuniors.queue-it.net/?c=bocajuniors&e=QUEUE_EVENT&cid=es-CL&q=QUEUEID
```
