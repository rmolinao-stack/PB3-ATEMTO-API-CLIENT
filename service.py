
import requests
import uuid
from typing import Any

from config import (
    API_KEY,
    MAX_PREGUNTA_CHARS,
    REQUEST_TIMEOUT_SECONDS,
    URL_BASE,
)

def _llamar(funcion, ruta: str, **kwargs) -> Any:
    """Devuelve el JSON de la API o {"api_error": {...}} (401, 404, 429, 504, red...) sin lanzar."""
    try:
        resp = funcion(
            f"{URL_BASE}{ruta}",
            params={"api_key": API_KEY},
            timeout=REQUEST_TIMEOUT_SECONDS,
            **kwargs,
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


def _post(ruta: str, body: dict[str, Any]) -> Any:
    return _llamar(requests.post, ruta, json=body)


def _get(ruta: str) -> Any:
    return _llamar(requests.get, ruta)


def _es_error(out: Any) -> bool:
    return isinstance(out, dict) and "api_error" in out


HISTORIAL_FIN = "--- FIN HISTORIAL DE MENSAJES ---"
NOTA_OMITIDOS = "[... mensajes anteriores omitidos por longitud ...]"
ROLES = {"user": "Usuario", "assistant": "Asistente"}


def _contenido_limpio(mensaje: dict[str, Any]) -> str:
    """El servidor guarda la pregunta tal cual se envió (con su historial): nos quedamos solo con la parte final."""
    contenido = (mensaje.get("content") or "").strip()
    return contenido.rpartition(HISTORIAL_FIN)[2].strip()


def _con_historial(thread_id: str, mensajes: list[dict[str, Any]], pregunta: str) -> str:
    """Antepone el historial (más recientes primero si no cabe) entre marcadores a la pregunta."""
    cabecera = f"--- HISTORIAL DE MENSAJES DE LA CONVERSACIÓN ID {thread_id} ---"
    lineas = [
        f"{ROLES.get(m.get('role'), m.get('role') or '?')}: {texto}"
        for m in mensajes
        if (texto := _contenido_limpio(m))
    ]
    if not lineas:
        return pregunta

    # +4 saltos de línea entre bloques; la nota se reserva siempre para simplificar
    presupuesto = MAX_PREGUNTA_CHARS - len(pregunta) - len(cabecera) - len(HISTORIAL_FIN) - len(NOTA_OMITIDOS) - 8
    elegidas: list[str] = []
    for linea in reversed(lineas):
        if presupuesto < len(linea) + 1:
            break
        presupuesto -= len(linea) + 1
        elegidas.insert(0, linea)
    if not elegidas:
        return pregunta
    if len(elegidas) < len(lineas):
        elegidas.insert(0, NOTA_OMITIDOS)

    return "\n".join([cabecera, *elegidas, HISTORIAL_FIN, "", pregunta])


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
        "api_error": None,
    }


def service_ejecutar_plan(
        estado: dict[str, Any], 
        mensaje: str, 
        thread_id: str) -> dict[str, Any]:
    """GET /threads/{id}/messages + POST /ask — auto_aprobar=False para conservar el flujo HITL manual."""
    historial = _get(f"/threads/{thread_id}/messages")
    if _es_error(historial):
        return {**estado, "api_error": historial["api_error"]}
    # Convertimos el historial a la lista de mensajes esperada
    if isinstance(historial, dict) and "messages" in historial:
        historial = historial["messages"]

    pregunta = _con_historial(thread_id, historial, mensaje)
    print("=" * 40)
    print(pregunta)
    print("=" * 40)

    out = _post(
        "/ask",
        {
            "pregunta": pregunta,
            "thread_id": thread_id,
            "auto_aprobar": False,
        },
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