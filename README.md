# ATeMto (API Client)

***PB3-ATEMTO-API-CLIENT*** *es un cliente de la API de **ATeMto** (proyecto servidor **PB3-ATEMTO-WITH-API**). No contiene lógica de agente, RAG ni acceso a LLM: todo el procesamiento ocurre en el servidor y este proyecto solo consume sus endpoints.*

**ATeMto** es un empleado sintético capaz de calcular el trayecto entre dos estaciones de la red ATM de Barcelona (metro, autobuses, Ferrocarrils, TRAMvia y Rodalies), calcular los abonos necesarios, informar de tarifas y condiciones de uso y calcular cuándo llegará el siguiente metro de TMB a una estación concreta.

Este cliente ofrece dos formas de interactuar con él:

* **Interfaz de chat en Streamlit** (`app_agent.py`): conversación con ATeMto, con aprobación manual del plan (HITL) desde la barra lateral y un panel de debug.
* **CLI de pruebas** (`main.py`): comprueba que la API está viva y lanza una pregunta de demostración mostrando respuesta e historial.

En cada turno del chat de Streamlit (`app_agent.py`) el cliente envía junto a la pregunta el historial del hilo (obtenido de la API) para dar contexto al agente. La CLI (`main.py --demo`) no lo hace: solo envía la pregunta.

## Estructura del proyecto

```text
PB3-ATEMTO-API-CLIENT/
├── app_agent.py        # Chat Streamlit: UI, HITL (aprobar/rechazar) y panel "Log (debug)".
├── service.py          # Capa de servicio: llamadas HTTP a la API, gestión de errores y construcción del historial.
├── config.py           # Carga de .env y parámetros (API_KEY, URL_BASE, timeouts, límite de pregunta).
├── main.py             # CLI de pruebas: --health y --demo.
├── requirements.txt    # Dependencias.
├── .env.example        # Plantilla de variables de entorno.
├── .gitignore
└── README.md
```

## Instalación del entorno de desarrollo y APIs

Obtención del código fuente via git:

```text
git clone https://github.com/rmolinao-stack/PB3-ATEMTO-API-CLIENT
```

Se recomienda el uso de un entorno virtual (probado con Python 3.13):

```text
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
```

Instalación de dependencias (`streamlit`, `requests`, `python-dotenv`):

```text
pip install -r requirements.txt
```

Creación del fichero de variables de entorno a partir de la plantilla:

```text
copy .env.example .env          # Linux/macOS: cp .env.example .env
```

### API Keys y variables de entorno necesarias

* **API_KEY**: clave de acceso a la API de ATeMto. Debe ser **la misma** que tiene configurada el servidor. Se envía como parámetro `api_key` en cada petición.
* **API_BASE_URL**: URL base donde corre la API, sin barra final (p. ej. `http://127.0.0.1:8000` en local o la URL de despliegue en Render).

Ambas variables son obligatorias: si falta alguna, la aplicación falla al arrancar. El fichero `.env` está en `.gitignore`; no debe subirse al repositorio.

Este cliente **no** necesita las claves de Gemini ni de TMB: las usa únicamente el servidor.

## Prerrequisito: servidor ATeMto en marcha

El cliente necesita la API de **PB3-ATEMTO-WITH-API** accesible en `API_BASE_URL`. En local:

```text
uvicorn api.app_api:app --reload --port 8000
```

(ejecutado en el proyecto servidor, que a su vez necesita su BBDD PostgreSQL; ver su README y memorias). Si el servidor está desplegado en un plan gratuito de Render, la primera petición puede tardar en "despertar" el servicio.

## Modos de Ejecución

### Modo 1: Chat en Streamlit

```text
streamlit run app_agent.py
```

Abre un chat con ATeMto. Funcionamiento:

* Cada conversación tiene un **ID de conversación** (`thread_id`, formato `ATM-xxxxxxxx`) editable en la barra lateral. Cambiarlo reinicia el chat local y permite retomar un hilo existente en el servidor.
* Cada mensaje se envía con `auto_aprobar=False`: si el agente propone un plan, queda **pendiente de aprobación** y el chat se bloquea hasta que se pulsa **Aprobar** o **Rechazar** en la barra lateral.
* El chat se bloquea también cuando la conversación se cierra (`done`) o el agente falla (`error`). Se reanuda con **Nueva conversación**.
* No hay límite de turnos en el cliente; cualquier límite lo decide la API.
* El expander **Log (debug)** muestra el estado de la sesión (ver "Gestión de errores").

### Modo 2: CLI de pruebas

```text
python main.py --health                      # Comprueba que la API está viva (GET /health)
python main.py --demo "¿Cómo llego de Sants a Diagonal?"   # Lanza solo la pregunta (sin histórico) y muestra respuesta + historial
```

`--demo` usa el hilo fijo `DEMO-MAIN-9999-afK77MnSs37` y `auto_aprobar=True`, y después consulta el historial del hilo.

> **Importante:** en `main.py`, cada `--demo` envía **únicamente la pregunta** a `POST /ask`; **NO** envía el histórico de la conversación (a diferencia de `app_agent.py`, que sí lo antepone a cada pregunta). El `GET /threads/{thread_id}/messages` posterior solo sirve para mostrar el historial por pantalla, no se reenvía al agente. Por tanto, cada demo se trata como una pregunta independiente, aunque se guarde en el mismo hilo.

## END-POINTS a los que conecta

Todos los endpoints protegidos reciben la clave como parámetro de consulta `?api_key=...`.

| Método | Ruta | Uso en el cliente | Requiere `api_key` | Usado por |
|--------|------|-------------------|:------------------:|-----------|
| GET | `/health` | Comprobar que la API está activa | No | `main.py --health` |
| GET | `/threads/{thread_id}/messages` | Obtener el historial del hilo (para anteponerlo a la pregunta y para mostrarlo en la demo) | Sí | `service.py`, `main.py --demo` |
| POST | `/ask` | Enviar una pregunta (`pregunta`, `thread_id`, `auto_aprobar`) | Sí | `service.py`, `main.py --demo` |
| POST | `/approve` | Aprobar o rechazar el plan pendiente (`thread_id`, `aprobado`) | Sí | `service.py` |

`/ask` y `/approve` devuelven `respuesta`, `thread_id`, `done`, `pendiente_hitl` y `error`. La documentación interactiva de la API está en `{API_BASE_URL}/docs`.

## Otros detalles relevantes

### Gestión de errores

Hay dos tipos de error distintos, que se muestran en el expander **Log (debug)**:

| Clave en el debug | Origen | Significado | Efecto |
|---|---|---|---|
| `error_http` | Cliente (`api_error` en el estado) | Falló la llamada HTTP: 401 (API key), 404, 400, 429 (rate limit), 503 (API key no configurada en servidor), 504 (timeout del turno) o error de red. Contiene `ruta`, `status` y `detalle`. | Recuperable: el chat sigue abierto y se puede reintentar. Solo se conserva el último. |
| `error_agente` | Servidor (`error` en la respuesta) | La llamada fue correcta (HTTP 200) pero el agente falló internamente (excepción del grafo o del LLM). | Bloquea la conversación: hay que pulsar **Nueva conversación**. |

### Historial de la conversación (solo en Streamlit)

En cada turno del chat de `app_agent.py` el cliente llama a `GET /threads/{thread_id}/messages` y antepone el historial a la pregunta entre los marcadores `--- HISTORIAL DE MENSAJES DE LA CONVERSACIÓN ID ... ---` y `--- FIN HISTORIAL DE MENSAJES ---`. El servidor limita `pregunta` a 20000 caracteres, así que si el historial no cabe se conservan los mensajes más recientes y se indica que los anteriores fueron omitidos. Del historial se descarta la parte de historial que el servidor ya guardó dentro de mensajes anteriores.

### Timeouts

* Un único timeout para todo el cliente: `REQUEST_TIMEOUT_SECONDS` en `config.py` (310 s por petición), algo por encima del timeout de turno del servidor (300 s por defecto) y del arranque en frío de Render. Lo usan tanto `service.py` (Streamlit) como `main.py` (CLI), incluido `--health`.

### Pendiente antes de entregar

* Limpiar la BBDD PostgreSQL del servidor, sobre todo el hilo `DEMO-MAIN-9999-afK77MnSs37` generado por `main.py --demo`.
