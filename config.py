import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "").lower().replace("@", "")

# Routing securely back to OpenRouter's free tier
LLM_API_KEY = os.getenv("OPENROUTER_API_KEY")
LLM_BASE_URL = "https://openrouter.ai/api/v1"
ACTIVE_MODEL = "openrouter/free"