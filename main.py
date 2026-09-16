import asyncio
import json
import logging
import os
import re
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ChatAction

import config
import prompts
import memory
import llm
import image_gen

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# --- Lightweight Web Server for Render Health Check ---
async def handle_ping(request):
    return web.Response(text="Zane is alive and running!")

async def start_webserver():
    """Runs a minimal HTTP ping endpoint so Render Web Service detects an open port."""
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/healthz", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health check webserver active on port {port}")

# --- Zane Message & Task Handlers ---
async def simulate_human_typing(chat_id: int, text: str):
    """Snappy typing delay capped at 1.0s to keep replies fast."""
    delay = min(max(len(text) * 0.012, 0.4), 1.0)
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    await asyncio.sleep(delay)

async def send_photo_task(chat_id: int, image_prompt: str):
    """Non-blocking background image delivery."""
    try:
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
        photo_result = await image_gen.generate_image(image_prompt)
        if photo_result:
            if isinstance(photo_result, bytes):
                photo_file = types.BufferedInputFile(photo_result, filename="zane_photo.jpg")
            else:
                photo_file = photo_result
            await bot.send_photo(chat_id=chat_id, photo=photo_file)
    except Exception as e:
        logger.error(f"Background image generation failed: {e}")

async def trigger_background_summarize(chat_id: int):
    """Refreshes structured JSON memory in background without blocking chat."""
    try:
        current_mem = await memory.get_memory_dict(chat_id)
        recent_history = await memory.get_recent_messages(chat_id, limit=25)
        
        conversation_dump = "\n".join([f"{m['role']}: {m['content']}" for m in recent_history])
        summary_prompt = (
            f"Prior Memory:\n{json.dumps(current_mem, indent=2)}\n\n"
            f"New Dialogue to Merge:\n{conversation_dump}\n\n"
            f"Output the updated JSON:"
        )
        
        raw_summary = await llm.generate_reply(
            messages=[{"role": "user", "content": summary_prompt}],
            system_prompt=prompts.SUMMARIZER_SYSTEM_PROMPT
        )
        
        healed_mem = memory.parse_and_heal_json(raw_summary, fallback=current_mem)
        await memory.update_structured_memory(chat_id, healed_mem)
        logger.info(f"Memory refreshed successfully for chat {chat_id}")
    except Exception as e:
        logger.error(f"Background summarization error: {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Hey... I'm here. Talk to me however you want. I remember everything.")

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    await memory.clear_history(message.chat.id)
    await message.answer("Memory wiped clean. Starting completely fresh with you.")

@dp.message(F.text)
async def handle_message(message: types.Message):
    chat_id = message.chat.id
    user_text = message.text.strip()
    
    # Handle group chats: ignore messages not addressing Zane
    if message.chat.type in ["group", "supergroup"]:
        bot_info = await bot.get_me()
        is_reply_to_bot = (
            message.reply_to_message 
            and message.reply_to_message.from_user.id == bot_info.id
        )
        has_mention = f"@{config.BOT_USERNAME}".lower() in message.text.lower()
        
        if not (is_reply_to_bot or has_mention):
            return
            
        user_text = re.sub(f"@{config.BOT_USERNAME}", "", user_text, flags=re.IGNORECASE).strip()

    await memory.save_message(chat_id, "user", user_text)
    
    # Fetch structured memory and recent history
    mem_dict = await memory.get_memory_dict(chat_id)
    memory_context = memory.format_memory_for_prompt(mem_dict)
    history = await memory.get_recent_messages(chat_id, limit=18)
    
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    
    full_system = f"{prompts.SYSTEM_PROMPT}\n\n{prompts.FEW_SHOT_EXAMPLES}\n\n{memory_context}"
    raw_response = await llm.generate_reply(messages=history, system_prompt=full_system)
    
    # Extract [IMG: ...] prompt if present
    image_prompt = None
    img_match = re.search(r"\[IMG:\s*(.*?)\]", raw_response, re.DOTALL)
    if img_match:
        image_prompt = img_match.group(1).strip()
        cleaned_response = re.sub(r"\[IMG:\s*.*?\]", "", raw_response).strip()
    else:
        cleaned_response = raw_response.strip()

    if not cleaned_response:
        cleaned_response = "Ahhh Wait... Error"

    # Double-texting dispatcher
    sub_messages = [m.strip() for m in cleaned_response.split("||") if m.strip()]
    if not sub_messages:
        sub_messages = [cleaned_response]

    for idx, part in enumerate(sub_messages):
        await simulate_human_typing(chat_id, part)
        await message.answer(part)
        if idx < len(sub_messages) - 1:
            await asyncio.sleep(0.25)

    # Fire non-blocking background task for image generation
    if image_prompt:
        asyncio.create_task(send_photo_task(chat_id, image_prompt))

    await memory.save_message(chat_id, "assistant", cleaned_response)

    # Periodic background memory update every 20 messages
    count = await memory.get_message_count(chat_id)
    if count > 0 and count % 20 == 0:
        asyncio.create_task(trigger_background_summarize(chat_id))

async def main():
    await memory.init_db()
    await start_webserver()
    print(f"Zane online. Backend: {config.ACTIVE_MODEL}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
