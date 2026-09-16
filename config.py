import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "").lower().replace("@", "")

LLM_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("OPENROUTER_API_KEY")
LLM_BASE_URL = "https://api.groq.com/openai/v1"
ACTIVE_MODEL = "openai/gpt-oss-20b"
