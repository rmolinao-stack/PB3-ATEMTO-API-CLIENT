"""Cliente CLI de la API ATeMto.

Uso:
  python main.py --health
  python main.py --demo "pregunta"
"""

import argparse
import json

import requests
from config import API_KEY, URL_BASE, REQUEST_TIMEOUT_SECONDS

def check_health() -> bool:
    """Comprueba que la API está activa antes de lanzar consultas."""
    try:
        resp = requests.get(f"{URL_BASE}/health", timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        print(f"[OK] API disponible en {URL_BASE} -> {resp.json()}")
        return True
    except requests.RequestException as e:
        print(f"[ERROR] No se pudo conectar con {URL_BASE}/health: {e}")
        return False


def demo_total(
    pregunta: str,
    thread_id: str,
    auto_aprobar: bool,
    api_key: str,
    api_base_url: str,
    request_timeout: int,
) -> None:
    """Envía un turno al endpoint POST /ask."""
    if not api_key:
        raise RuntimeError("Falta API_KEY en el archivo .env del cliente.")

    url = f"{api_base_url}/ask"
    params = {"api_key": api_key}
    payload = {
        "pregunta": pregunta,
        "thread_id": thread_id,
        "auto_aprobar": auto_aprobar,
    }

    try:
        response = requests.post(
            url,
            params=params,
            json=payload,
            timeout=request_timeout,
        )
        response.raise_for_status()

        print("="*60)
        print("="*25 + " RESPUESTA " + "="*25)
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        print("="*60)

        url = f"{api_base_url}/threads/{thread_id}/messages"
   
        response2 = requests.get(
            url,
            params=params,
            timeout=request_timeout,
        )
        response2.raise_for_status()

        print()
        print("="*20 + " HISTORIAL THREAD " + thread_id + " " + "="*20)
        print(json.dumps(response2.json(), indent=2, ensure_ascii=False))
        print("="*20 + " FIN HISTORIAL THREAD " + thread_id + " " + "="*20)

    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "N/A"
        detail = e.response.text if e.response is not None else str(e)
        print(f"\n[HTTP {status}] Error en la petición: {detail}")
    except requests.Timeout:
        print(f"\n[TIMEOUT] La API tardó más de {request_timeout}s en responder.")
    except requests.RequestException as e:
        print(f"\n[ERROR DE RED] {e}")

def main() -> None:
    
    parser = argparse.ArgumentParser(
        description="""
        Cliente de la API ATEMTO para pruebas desde línea de comandos.
        """
    )

    ############ RMO: PARAMETROS ###################
    parser.add_argument("--health", action="store_true", help="Verifica si la API está viva")
    parser.add_argument("--demo", type=str, help="Lanza la pregunta sobre el thread DEMO-MAIN-9999-afK77MnSs37 y devuelve el historial de DEMO-MAIN-9999-afK77MnSs37")

    args = parser.parse_args()
  
   

    if args.health:
        if not check_health():
            print("La API no está disponible.")
        else:
            print("La API está disponible.")
    if args.demo:
        print("Opción demo seleccionada ...")
        thread_id = "DEMO-MAIN-9999-afK77MnSs37"
        pregunta = args.demo
        demo_total(pregunta=pregunta, 
                              thread_id=thread_id, 
                              auto_aprobar=True, 
                              api_key=API_KEY, 
                              api_base_url=URL_BASE, 
                              request_timeout=REQUEST_TIMEOUT_SECONDS)
        
        
        

if __name__ == "__main__":
    main()