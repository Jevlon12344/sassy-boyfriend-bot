import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "").lower().replace("@", "")

# Groq endpoint & credentials
LLM_API_KEY = os.getenv("GROQ_API_KEY")
LLM_BASE_URL = "https://api.groq.com/openai/v1"
ACTIVE_MODEL = "llama-3.3-70b-versatile"
