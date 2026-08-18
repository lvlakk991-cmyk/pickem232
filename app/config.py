import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
}
DB_PATH = os.getenv("DB_PATH", "pickem.db")
WEBAPP_URL = os.getenv("WEBAPP_URL", "").rstrip("/")
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

# --- Points system ---
POINTS_WINNER = 10
POINTS_SCORE = 15
POINTS_MVP = 20
SUBSCRIBE_BONUS = 100

# --- Achievement tiers ---
ACHIEVEMENT_TIERS = [
    {"name": "BEGINNER", "points": 150},
    {"name": "PRO", "points": 200},
    {"name": "CHEATER", "points": 350},
    {"name": "GOD", "points": 500},
]
MAX_TIER_POINTS = ACHIEVEMENT_TIERS[-1]["points"]
