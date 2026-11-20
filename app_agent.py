"""App Streamlit — cliente del grafo multiagente (ATM).

  streamlit run app_agent.py
"""

from typing import Any

import requests
import streamlit as st
import uuid

from config import MAX_TURNS_DEFAULT, URL_BASE, API_KEY, REQUEST_TIMEOUT_SECONDS


st.set_page_config(
    page_title="ATeMto - Tu agente de ATM",
    page_icon="🚆",
    layout="centered",
)

SALUDO = (
    "Hola — soy ATeMto, tu agente planificador de la red de transporte de ATM de Barcelona. "
    "Soy capaz de darte una ruta eficiente entre dos estaciones de la red ATM, "
    "darte el mejor abono de transporte según tus necesidades e incluso "
    "decirte cuando va llegar el siguiente tren (solo estaciones de TMB). "
    "Preguntame y te daré un plan listo para que lo apruebes en la barra lateral."
)

def _post(ruta: str, body: dict[str, Any]) -> dict[str, Any]:
    """Devuelve el JSON de la API o {"api_error": {...}} (401, 404, 429, 504, red...) sin lanzar."""
    try:
        resp = requests.post(
            f"{URL_BASE}{ruta}",
            params={"api_key": API_KEY},
            json=body,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return {"api_error": {"ruta": ruta, "status": None, "detalle": f"{type(exc).__name__}: {exc}"}}

    if not resp.ok:
        try:
            detalle = resp.json().get("detail", resp.text)
        except (ValueError, AttributeError):
            detalle = resp.text
        return {"api_error": {"ruta": ruta, "status": resp.status_code, "detalle": detalle}}
    return resp.json()


def service_nuevo_thread_id() -> str:
    return f"ATM-{uuid.uuid4().hex[:8]}"


def service_crear_estado(thread_id: str) -> dict[str, Any]:
    """Estado local mínimo; el estado real del agente vive en el servidor (por thread_id)."""
    return {
        "thread_id": thread_id,
        "respuesta": "",
        "plan": [],
        "done": False,
        "error": None,
        "pendiente_hitl": False,
        "turnos": 0,
        "api_error": None,
    }


def service_ejecutar_plan(estado: dict[str, Any], mensaje: str, thread_id: str) -> dict[str, Any]:
    """POST /ask — auto_aprobar=False para conservar el flujo HITL manual."""
    out = _post(
        "/ask",
        {"pregunta": mensaje, "thread_id": thread_id, "auto_aprobar": False},
    )
    if "api_error" in out:
        # No cierra la conversación: el usuario puede reintentar
        return {**estado, "api_error": out["api_error"]}
    return {
        **estado,
        "respuesta": out["respuesta"],
        "done": out["done"],
        "pendiente_hitl": out["pendiente_hitl"],
        "error": out["error"],
        "turnos": estado["turnos"] + 1,
        "api_error": None,
    }


def service_aprobar_plan(thread_id: str, aprobado: bool, estado: dict[str, Any]) -> dict[str, Any]:
    """POST /approve."""
    out = _post("/approve", {"thread_id": thread_id, "aprobado": aprobado})
    if "api_error" in out:
        return {**estado, "api_error": out["api_error"]}
    return {
        **estado,
        "respuesta": out["respuesta"],
        "done": out["done"],
        "pendiente_hitl": out["pendiente_hitl"],
        "error": out["error"],
        "api_error": None,
    }


def _reset(thread_id: str | None = None) -> None:
    thread_id = thread_id or service_nuevo_thread_id()
    st.session_state.messages = [{"role": "assistant", "content": SALUDO}]
    st.session_state.thread_id = thread_id
    st.session_state.agent_state = service_crear_estado(thread_id)


def _texto_api_error(api_error: dict[str, Any]) -> str:
    status = api_error.get("status")
    cabecera = f"Error {status}" if status else "No se pudo contactar con la API"
    return f"⚠️ **{cabecera}** en `{api_error.get('ruta')}`: {api_error.get('detalle')}"


def _resolver_hitl(aprobado: bool) -> None:
    st.session_state.agent_state = service_aprobar_plan(
        st.session_state.thread_id, aprobado, st.session_state.agent_state
    )
    api_error = st.session_state.agent_state.get("api_error")
    if api_error:
        st.session_state.messages.append(
            {"role": "assistant", "content": _texto_api_error(api_error)}
        )
        return
    por_defecto = "Plan aprobado." if aprobado else "Plan rechazado."
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": st.session_state.agent_state.get("respuesta") or por_defecto,
        }
    )


if "messages" not in st.session_state:
    _reset()

with st.sidebar:
    st.header("Configuración")
    max_turns = st.slider(
        "Max Turns (turnos de la conversación)",
        min_value=1,
        max_value=12,
        value=MAX_TURNS_DEFAULT,
    )
    # La key incluye el id para que el campo se refresque cuando _reset() genera uno nuevo
    thread_id_input = st.text_input(
        "ID Conversación",
        value=st.session_state.thread_id,
        key=f"thread_id_input_{st.session_state.thread_id}",
        help="Puedes escribir un ID a mano (p. ej. para retomar un hilo del servidor). "
        "Al cambiarlo se reinicia el chat local.",
    ).strip()
    if thread_id_input and thread_id_input != st.session_state.thread_id:
        _reset(thread_id_input)
        st.rerun()

    estado_side = st.session_state.get("agent_state") or {}
    if estado_side.get("pendiente_hitl"):
        st.divider()
        st.subheader("HITL — aprobar plan")
        for item in estado_side.get("plan") or []:
            st.markdown(f"- {item}")
        c1, c2 = st.columns(2)
        if c1.button("Aprobar", use_container_width=True, type="primary"):
            _resolver_hitl(True)
            st.rerun()
        if c2.button("Rechazar", use_container_width=True):
            _resolver_hitl(False)
            st.rerun()

    if st.button("Nueva conversación", use_container_width=True):
        _reset()
        st.rerun()

st.title(":gray[AT]e:gray[M]to - Agente de transporte ATM")
st.caption("Multiagente · ATM")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

estado = st.session_state.agent_state
chat_bloqueado = bool(estado.get("done") or estado.get("error"))
turnos_hechos = len(estado.get("traza") or [])
hitl_bloquea = bool(estado.get("pendiente_hitl"))

if chat_bloqueado:
    st.info("Conversación cerrada (`done` o `error`). Pulsa «Nueva conversación».")
elif hitl_bloquea:
    st.warning("Plan pendiente de aprobación — usa los botones de la barra lateral.")
elif turnos_hechos >= max_turns:
    st.warning("Has alcanzado `max_turns`. Pulsa «Nueva conversación» o sube el límite.")

if prompt := st.chat_input(
    "Escribe tu mensaje…",
    disabled=chat_bloqueado or hitl_bloquea or turnos_hechos >= max_turns,
):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Grafo multiagente (especialistas + tools)…"):
            estado = service_ejecutar_plan(
                estado,
                prompt,
                st.session_state.thread_id,
            )
            st.session_state.agent_state = estado

        if estado.get("error"):
            st.error(estado["error"])

        if estado.get("api_error"):
            texto = _texto_api_error(estado["api_error"])
        else:
            texto = estado.get("respuesta") or "(Sin respuesta)"
        plan = estado.get("plan") or []
        if plan:
            if estado.get("pendiente_hitl"):
                etiqueta = "Plan (pendiente de aprobación)"
            elif estado.get("done"):
                etiqueta = "Plan"
            else:
                etiqueta = "Plan (borrador)"
            bullets = "\n".join(f"- {item}" for item in plan)
            texto = f"{texto}\n\n**{etiqueta}:**\n{bullets}"
        st.markdown(texto)
        st.session_state.messages.append({"role": "assistant", "content": texto})

    # Sidebar ya se dibujó arriba: hay que rerun para mostrar Aprobar/Rechazar
    if estado.get("pendiente_hitl") or estado.get("done") or estado.get("error"):
        st.rerun()

with st.expander("Estado / log / tools (debug)"):
    st.json(
        {
            "thread_id": st.session_state.get("thread_id"),
            "plan": st.session_state.agent_state.get("plan"),
            "pendiente_hitl": st.session_state.agent_state.get("pendiente_hitl"),
            "plan_aprobado": st.session_state.agent_state.get("plan_aprobado"),
            "done": st.session_state.agent_state.get("done"),
            "log": st.session_state.agent_state.get("log"),
            "error": st.session_state.agent_state.get("error"),
            "api_error": st.session_state.agent_state.get("api_error"),
            "traza": st.session_state.agent_state.get("traza"),
        }
    )