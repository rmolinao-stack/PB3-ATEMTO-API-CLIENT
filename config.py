
import os

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY").strip()
URL_BASE = os.getenv("API_BASE_URL").rstrip("/")

REQUEST_TIMEOUT = 10

MAX_TURNS_DEFAULT = 6
# Límite de AskIn.pregunta en el servidor (api/schemas.py): historial + pregunta deben caber
MAX_PREGUNTA_CHARS = 20000
# El servidor corta cada turno a ASK_TIMEOUT_SECONDS (300 por defecto); Render gratis
# además puede tardar en "despertar", así que el cliente espera un poco más.
REQUEST_TIMEOUT_SECONDS = 310