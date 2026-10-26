import os
from dotenv import load_dotenv

load_dotenv()

# --- IDs principaux (donnés par l'utilisateur) ---
GUILD_ID = int(os.getenv("GUILD_ID", "1553129363858530465"))
TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID", "1560529185880154263"))
STAFF_ROLE_ID = int(os.getenv("STAFF_ROLE_ID", "1564261898935992382"))

# --- Optionnels ---
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
LOG_CHANNEL_ID = int(LOG_CHANNEL_ID) if LOG_CHANNEL_ID and LOG_CHANNEL_ID.isdigit() else None

ANNOUNCE_CHANNEL_ID = os.getenv("ANNOUNCE_CHANNEL_ID")
ANNOUNCE_CHANNEL_ID = int(ANNOUNCE_CHANNEL_ID) if ANNOUNCE_CHANNEL_ID and ANNOUNCE_CHANNEL_ID.isdigit() else None

TICKET_COOLDOWN_SECONDS = int(os.getenv("TICKET_COOLDOWN_SECONDS", "300"))
AUTO_CLOSE_DAYS = int(os.getenv("AUTO_CLOSE_DAYS", "7"))

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
BOT_ACTIVITY = os.getenv("BOT_ACTIVITY", "MP pour ouvrir un ticket ✈️")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Constantes visuelles Air France ---
COLOR_AF_BLUE = 0x002395
COLOR_AF_RED = 0xED2939
COLOR_AF_WHITE = 0xFFFFFF
COLOR_SUCCESS = 0x2ECC71
COLOR_WARNING = 0xF39C12
COLOR_ERROR = 0xE74C3C

# --- Limites stockage ---
MAX_ATTACHMENT_SIZE_MB = 25
TRANSCRIPT_COMPRESSION = os.getenv("TRANSCRIPT_COMPRESSION", "true").lower() == "true"
DB_PATH = os.getenv("DB_PATH", "data/tickets.db")
TRANSCRIPT_DIR = "data/transcripts"

# --- Messages ---
FOOTER_TEXT = "Air France Helpine • Système de tickets MP"
