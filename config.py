import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Charge config.json si présent (permet .env + config.json) ---
# Priorité : 1) variable d'environnement (.env) 2) config.json 3) défaut codé en dur
_JSON_PATH = Path("config.json")
_JSON_CONFIG: dict = {}
if _JSON_PATH.exists():
    try:
        with _JSON_PATH.open("r", encoding="utf-8") as f:
            _JSON_CONFIG = json.load(f)
    except Exception as e:
        print(f"[config] ⚠️ Impossible de lire config.json : {e} — on ignore et on utilise .env/défauts")

def _get(key: str, default=None):
    """Récupère une valeur avec priorité ENV > JSON > défaut"""
    # ENV a priorité (permet override docker/heroku)
    env_val = os.getenv(key)
    if env_val not in (None, ""):
        return env_val
    if key in _JSON_CONFIG and _JSON_CONFIG[key] not in (None, ""):
        return _JSON_CONFIG[key]
    return default

def _get_int(key: str, default: int) -> int:
    val = _get(key, default)
    if val is None:
        return None
    try:
        return int(val)
    except:
        return default

def _get_optional_int(key: str):
    val = _get(key, None)
    if val is None or val == "" or str(val).lower() == "null":
        return None
    try:
        return int(val)
    except:
        return None

# --- IDs principaux (donnés par l'utilisateur) ---
GUILD_ID = _get_int("GUILD_ID", 1553129363858530465)
TICKET_CATEGORY_ID = _get_int("TICKET_CATEGORY_ID", 1560529185880154263)
STAFF_ROLE_ID = _get_int("STAFF_ROLE_ID", 1564261898935992382)

# --- Optionnels ---
LOG_CHANNEL_ID = _get_optional_int("LOG_CHANNEL_ID")
ANNOUNCE_CHANNEL_ID = _get_optional_int("ANNOUNCE_CHANNEL_ID")

TICKET_COOLDOWN_SECONDS = _get_int("TICKET_COOLDOWN_SECONDS", 300)
AUTO_CLOSE_DAYS = _get_int("AUTO_CLOSE_DAYS", 7)

DISCORD_TOKEN = _get("DISCORD_TOKEN", "")
BOT_ACTIVITY = _get("BOT_ACTIVITY", "MP pour ouvrir un ticket ✈️")
LOG_LEVEL = _get("LOG_LEVEL", "INFO")

# --- Constantes visuelles Air France ---
COLOR_AF_BLUE = 0x002395
COLOR_AF_RED = 0xED2939
COLOR_AF_WHITE = 0xFFFFFF
COLOR_SUCCESS = 0x2ECC71
COLOR_WARNING = 0xF39C12
COLOR_ERROR = 0xE74C3C

# --- Limites stockage ---
MAX_ATTACHMENT_SIZE_MB = 25
_raw_compression = _get("TRANSCRIPT_COMPRESSION", True)
if isinstance(_raw_compression, bool):
    TRANSCRIPT_COMPRESSION = _raw_compression
else:
    TRANSCRIPT_COMPRESSION = str(_raw_compression).lower() == "true"

DB_PATH = _get("DB_PATH", "data/tickets.db")
TRANSCRIPT_DIR = "data/transcripts"

# --- Messages ---
FOOTER_TEXT = "Air France Helpine • Système de tickets MP"

# --- Debug au lancement (sans leak token) ---
def log_config_source():
    src = []
    if _JSON_PATH.exists():
        src.append("config.json")
    if Path(".env").exists():
        src.append(".env")
    if not src:
        src.append("défauts codés")
    return ", ".join(src)
