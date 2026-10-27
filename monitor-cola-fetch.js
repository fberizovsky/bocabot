// Paso 1: preparar los datos fijos que usa Queue-it para identificar la cola.
const { randomUUID } = require("node:crypto");

const LOGIN_URL = process.env.BOCA_LOGIN_URL || "https://bocasocios.bocajuniors.com.ar/auth/login";
const QUEUE_HOST = process.env.QUEUE_HOST || "https://bocajuniors.queue-it.net";
const CUSTOMER = process.env.QUEUE_CUSTOMER || "bocajuniors";
const EVENT_ID = process.env.QUEUE_EVENT || "e20261101adh";
const QUEUE_LABEL = process.env.QUEUE_LABEL || "Boca Socios";
const REDIRECT_TARGET =
  process.env.QUEUE_TARGET || "https://bocasocios-gw.bocajuniors.com.ar/queueit/redirect";
const DEFAULT_INTERVAL_MS = Number(process.env.POLL_INTERVAL_MS) || 40_000;

// Paso 2: conservar las cookies entre peticiones, igual que haría un navegador.
// No se escriben en disco y se eliminan al terminar el proceso.
class CookieJar {
  #cookies = new Map();

  addFromResponse(response) {
    const values = response.headers.getSetCookie?.() ?? [];
    for (const value of values) {
      const [pair] = value.split(";", 1);
      const separator = pair.indexOf("=");
      if (separator > 0) {
        this.#cookies.set(pair.slice(0, separator), pair.slice(separator + 1));
      }
    }
  }

  header() {
    return [...this.#cookies.entries()].map(([name, value]) => `${name}=${value}`).join("; ");
  }
}

// Paso 3: enviar una petición HTTP incluyendo las cookies de la sesión actual.
async function request(url, options, cookies) {
  const headers = new Headers(options.headers);
  const cookie = cookies.header();
  if (cookie) headers.set("cookie", cookie);
  const response = await fetch(url, { ...options, headers });
  cookies.addFromResponse(response);
  return response;
}

// Paso 4: validar la respuesta del servidor y convertirla desde JSON.
async function readJson(response) {
  const body = await response.text();
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}: ${body.slice(0, 500)}`);
  }
  try {
    return JSON.parse(body);
  } catch {
    throw new Error(`La respuesta no es JSON: ${body.slice(0, 500)}`);
  }
}

// Paso 5: mostrar el tiempo restante y los demás datos devueltos por status.
function printStatus(status) {
  const ticket = status.ticket ?? {};
  const now = new Date().toLocaleTimeString("es-AR");
  console.log(
    `[${now}] faltan: ${ticket.whichIsIn ?? "sin dato"} | ` +
      `hora estimada: ${ticket.expectedServiceTime ?? "sin dato"} | ` +
      `actualizado: ${ticket.lastUpdated ?? "sin dato"} | ` +
      `estado: ${status.forecastStatus ?? "sin dato"}`,
  );
}

async function main() {
  const cookies = new CookieJar();

  // Paso 6: iniciar la sesión HTTP con la página de login.
  // Esto no inicia sesión de usuario ni abre un navegador; solo obtiene cookies iniciales.
  const loginResponse = await request(LOGIN_URL, { method: "GET" }, cookies);
  if (!loginResponse.ok) {
    throw new Error(`No se pudo abrir la página inicial: ${loginResponse.status}`);
  }

  // Paso 7: construir el endpoint que asigna un lugar en la cola.
  const enqueueUrl = new URL(
    `/spa-api/queue/${CUSTOMER}/${EVENT_ID}/enqueue`,
    QUEUE_HOST,
  );
  enqueueUrl.searchParams.set("cid", "es-ES");
  enqueueUrl.searchParams.set("l", QUEUE_LABEL);
  enqueueUrl.searchParams.set("t", REDIRECT_TARGET);

  // Paso 8: usar las cabeceras y el cuerpo esperados por la API.
  const commonHeaders = {
    accept: "application/json, text/javascript, */*; q=0.01",
    "content-type": "application/json",
    "x-requested-with": "XMLHttpRequest",
    referer: `${QUEUE_HOST}/`,
  };

  // Paso 9: pedir la entrada a la cola y obtener el queueId.
  const enqueueResponse = await request(
    enqueueUrl,
    {
      method: "POST",
      headers: commonHeaders,
      body: "{}",
    },
    cookies,
  );
  const enqueue = await readJson(enqueueResponse);
  const queueId = enqueue.queueId;

  if (!queueId) {
    throw new Error(`La respuesta enqueue no contiene queueId: ${JSON.stringify(enqueue)}`);
  }

  // Paso 10: construir el endpoint de estado usando el queueId obtenido.
  const statusUrl = new URL(
    `/spa-api/queue/${CUSTOMER}/${EVENT_ID}/${encodeURIComponent(queueId)}/status`,
    QUEUE_HOST,
  );
  statusUrl.searchParams.set("cid", "es-ES");
  statusUrl.searchParams.set("l", QUEUE_LABEL);
  statusUrl.searchParams.set("t", REDIRECT_TARGET);
  statusUrl.searchParams.set("seid", randomUUID());
  statusUrl.searchParams.set("sets", Date.now().toString());

  console.log(`queueId: ${queueId}`);
  console.log(`Consultando: ${statusUrl.origin}${statusUrl.pathname}`);

  // Paso 11: consultar status repetidamente hasta que Queue-it indique que se puede continuar.
  let intervalMs = DEFAULT_INTERVAL_MS;
  while (true) {
    const statusResponse = await request(
      statusUrl,
      {
        method: "POST",
        headers: commonHeaders,
        body: "{}",
      },
      cookies,
    );
    const status = await readJson(statusResponse);
    printStatus(status);

    if (status.redirectUrl || status.forecastStatus === "Redirect") {
      console.log("La cola indicó que ya se puede continuar.");
      break;
    }

    intervalMs = Number(status.updateInterval) || intervalMs;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}

main().catch((error) => {
  console.error(`Error monitoreando la cola: ${error.message}`);
  process.exitCode = 1;
});
