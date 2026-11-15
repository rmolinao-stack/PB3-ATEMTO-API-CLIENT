
import os

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY").strip()
URL_BASE = os.getenv("API_BASE_URL").rstrip("/")

REQUEST_TIMEOUT = 10