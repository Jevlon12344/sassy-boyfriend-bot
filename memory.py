import aiosqlite
import json
import logging
import re
from typing import Dict, List

DB_PATH = "data/memory.db"
logger = logging.getLogger(__name__)

DEFAULT_MEMORY = {
    "user_profile": "No profile recorded yet.",
    "relationship_dynamic": "Sassy, teasing, and playful banter.",
    "intimacy_preferences": "No specific boundaries established yet.",
    "current_context": "Casual conversation."
}

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS structured_memory (
                chat_id INTEGER PRIMARY KEY,
                memory_json TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def save_message(chat_id: int, role: str, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
            (chat_id, role, content)
        )
        await db.commit()

async def get_recent_messages(chat_id: int, limit: int = 20) -> List[Dict[str, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit)
        )
        rows = await cursor.fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

async def clear_history(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        await db.execute("DELETE FROM structured_memory WHERE chat_id = ?", (chat_id,))
        await db.commit()

async def get_memory_dict(chat_id: int) -> Dict[str, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT memory_json FROM structured_memory WHERE chat_id = ?",
            (chat_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return DEFAULT_MEMORY.copy()
        try:
            return json.loads(row[0])
        except Exception:
            return DEFAULT_MEMORY.copy()

def format_memory_for_prompt(mem: Dict[str, str]) -> str:
    return (
        f"### Zane's Mental Notes About Partner:\n"
        f"- Profile: {mem.get('user_profile', 'None')}\n"
        f"- Dynamics & Jokes: {mem.get('relationship_dynamic', 'Playful')}\n"
        f"- Intimacy & Turn-ons: {mem.get('intimacy_preferences', 'None')}\n"
        f"- Ongoing Context: {mem.get('current_context', 'Casual')}"
    )

def parse_and_heal_json(raw_text: str, fallback: Dict[str, str]) -> Dict[str, str]:
    """Self-healing extractor: isolates JSON even if wrapped in conversation or markdown."""
    try:
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()
        
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)
            
        data = json.loads(cleaned)
        return {
            "user_profile": str(data.get("user_profile", fallback.get("user_profile", ""))),
            "relationship_dynamic": str(data.get("relationship_dynamic", fallback.get("relationship_dynamic", ""))),
            "intimacy_preferences": str(data.get("intimacy_preferences", fallback.get("intimacy_preferences", ""))),
            "current_context": str(data.get("current_context", fallback.get("current_context", "")))
        }
    except Exception as e:
        logger.warning(f"Memory parse failed: {e}. Preserving prior memory state.")
        return fallback

async def update_structured_memory(chat_id: int, new_memory: Dict[str, str]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO structured_memory (chat_id, memory_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id) DO UPDATE SET
                memory_json = excluded.memory_json,
                updated_at = excluded.updated_at
        """, (chat_id, json.dumps(new_memory)))
        await db.commit()

async def get_message_count(chat_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM messages WHERE chat_id = ?", (chat_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0