# Monitores de fila Boca Socios

Este proyecto incluye tres monitores que obtienen un `queueId` y monitorean el tiempo restante de la fila virtual sin abrir un navegador:

- `monitor-cola.py`: Python, sin dependencias externas.
- `monitor-cola.sh`: Bash usando `curl` y `jq`.
- `monitor-cola-fetch.js`: Node.js usando `fetch`.

## Requisitos de Python

- Python 3.9 o superior.
- Conexión a internet.

El monitor de Python usa únicamente la biblioteca estándar. No requiere `pip` ni un entorno virtual.

```bash
python3 monitor-cola.py
```

## Requisitos de curl y jq

```bash
sudo apt install curl jq
```

Ejecutar:

```bash
./monitor-cola.sh
```

El script Bash necesita permisos de ejecución. Si fuera necesario:

```bash
chmod +x monitor-cola.sh
```

## Monitor Node.js

Requiere Node.js 18 o superior:

```bash
node monitor-cola-fetch.js
```

## Flujo común

Los tres monitores:

1. Solicita la página inicial para obtener las cookies de sesión.
2. Envía una petición `POST` a `enqueue`.
3. Obtiene el `queueId` devuelto por Queue-it.
4. Consulta periódicamente el endpoint `status`.
5. Muestra `whichIsIn`, la hora estimada y el estado de la cola.

Ejemplo:

```text
queueId: 88e7866c-e667-46b6-95ad-8912dbe30b81
Consultando: https://bocajuniors.queue-it.net/spa-api/queue/bocajuniors/e20261016adh/88e7866c-e667-46b6-95ad-8912dbe30b81/status
[18:06:06] faltan: 3 minutos | hora estimada: 18:09 | actualizado: 18:06:06 | estado: InLine
```

Para detenerlo:

```text
Ctrl+C
```

## Dashboard para múltiples monitores

Para lanzar y ver 100 monitores desde una sola terminal:

```bash
chmod +x monitor-cola-dashboard.sh
./monitor-cola-dashboard.sh
```

Cada fila muestra el estado, `queueId`, posición aproximada, hora estimada y
estado de una instancia. Se detienen todos los monitores con `Ctrl+C`.

La cantidad se puede indicar como primer argumento:

```bash
./monitor-cola-dashboard.sh 20
```

También se puede configurar el intervalo entre lanzamientos. Esto evita enviar
100 solicitudes iniciales exactamente al mismo tiempo:

```bash
MONITOR_LAUNCH_DELAY=0.5 ./monitor-cola-dashboard.sh 100
```

El dashboard usa las mismas variables de entorno que `monitor-cola.sh`, por
ejemplo:

```bash
QUEUE_EVENT=otro_evento ./monitor-cola-dashboard.sh
```

### Dashboard web local

También se puede abrir una interfaz HTML en el navegador:

```bash
chmod +x monitor-cola-web.sh
./monitor-cola-web.sh
```

Después de iniciar, abrir [http://127.0.0.1:8765](http://127.0.0.1:8765). La
página se actualiza automáticamente cada segundo y el servidor solo escucha en
la computadora local. La cantidad se puede indicar como argumento:

```bash
./monitor-cola-web.sh 20
```

Para usar otro puerto:

```bash
./monitor-cola-web.sh 100 --port 9000
```

Se detienen el servidor y todos los monitores con `Ctrl+C`.

## Disponibilidad de plateas

El script `plateas/consultar-disponibilidad.js` consulta las secciones del
evento y muestra si alguna tiene `hayDisponibilidad: true`. Requiere Node.js
18 o superior y recibir el token actual mediante una variable de entorno:

```bash
export BOCA_BEARER_TOKEN='token-sin-el-prefijo-Bearer'
export BOCA_COOKIE='cookie1=valor1; cookie2=valor2'
node plateas/consultar-disponibilidad.js
```

Las cookies son opcionales, pero pueden ser necesarias si el endpoint las
exige. Para consultar periódicamente, indicar el intervalo en segundos:

```bash
PLATEAS_INTERVAL_SECONDS=30 node plateas/consultar-disponibilidad.js
```

No guardes el Bearer ni las cookies en archivos versionados. El token incluido
en una petición compartida debe considerarse expuesto y conviene renovarlo.

## Configuración opcional

Se pueden sobrescribir los valores predeterminados usando variables de entorno:

| Variable | Valor predeterminado | Uso |
| --- | --- | --- |
| `BOCA_LOGIN_URL` | `https://bocasocios.bocajuniors.com.ar/auth/login` | Página inicial |
| `QUEUE_HOST` | `https://bocajuniors.queue-it.net` | Servidor de Queue-it |
| `QUEUE_CUSTOMER` | `bocajuniors` | Cliente de Queue-it |
| `QUEUE_EVENT` | `e20261016adh` | Evento de la fila |
| `QUEUE_LABEL` | `Boca Socios` | Etiqueta enviada a Queue-it |
| `QUEUE_TARGET` | `https://bocasocios-gw.bocajuniors.com.ar/queueit/redirect` | URL de retorno |
| `POLL_INTERVAL_MS` | El intervalo indicado por el servidor, normalmente 40000 ms | Intervalo mínimo entre consultas |

Ejemplo para consultar cada 10 segundos:

```bash
POLL_INTERVAL_MS=10000 python3 monitor-cola.py
```

El monitor Bash fuerza el formato decimal con punto para que `sleep` funcione
también en sistemas configurados con locales que usan coma decimal, como
`es_AR`.

Ejemplo cambiando el evento:

```bash
QUEUE_EVENT=otro_evento ./monitor-cola.sh
```

## Cómo averiguar el `EVENT_ID` de un evento próximo

El `EVENT_ID` es el identificador interno de la campaña de Queue-it. No se
puede calcular de forma confiable a partir de la fecha del evento. Para
obtenerlo, hay que observar una petición real del sitio cuando la fila virtual
se publique o se active.

1. Abrir la página donde se publicará la venta o inscripción.
2. Presionar `F12` y abrir la pestaña **Network / Red**.
3. Activar **Preserve log / Conservar registro**.
4. Filtrar las peticiones por `queue`, `enqueue`, `queue-it` o `spa-api`.
5. Buscar una URL similar a:

   ```text
   https://bocajuniors.queue-it.net/spa-api/queue/bocajuniors/e20261016adh/enqueue
   ```

   El texto ubicado después de `bocajuniors/` y antes de `/enqueue` es el
   `EVENT_ID`. En este ejemplo es `e20261016adh`.

También puede aparecer en una URL con un parámetro `e`:

```text
https://bocajuniors.queue-it.net/?c=bocajuniors&e=e20261016adh&cid=es-ES
```

En ese caso, el valor del parámetro `e` es el `EVENT_ID`.

Una vez identificado, se puede ejecutar el monitor sin modificar los archivos:

```bash
QUEUE_EVENT=e20261016adh ./monitor-cola.sh
```

O usando Python:

```bash
QUEUE_EVENT=e20261016adh python3 monitor-cola.py
```

`EVENT_ID` identifica el evento o la cola general. En cambio, `queueId` es el
identificador individual de un lugar dentro de esa cola y lo devuelve la
petición `enqueue`. Si el evento todavía no fue creado o publicado por el
organizador, no hay una forma segura de deducir su `EVENT_ID`; normalmente
aparece poco antes de habilitar la venta.

## Datos utilizados

La respuesta de `enqueue` devuelve el identificador de la fila:

```json
{
  "queueId": "..."
}
```

Luego, `status` devuelve el tiempo restante:

```json
{
  "ticket": {
    "whichIsIn": "3 minutos",
    "expectedServiceTime": "18:09"
  }
}
```

En Python y Node.js las cookies se mantienen únicamente en memoria. El script Bash usa un archivo temporal que se elimina automáticamente al salir.
