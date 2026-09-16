import asyncio
import logging
import re
from openai import AsyncOpenAI
import config

logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    base_url=config.LLM_BASE_URL,
    api_key=config.LLM_API_KEY
)

IN_CHARACTER_FALLBACKS = [
    "fuck, connection is terrible right now || what were you saying? -",
    "sorry, phone completely lagged out for a second- || say that again?",
    "signal dropped out on me || tell me again, I'm listening -"
]

async def generate_reply(messages: list, system_prompt: str = None) -> str:
    """Sends context to the endpoint with an automatic retry loop to fight API congestion."""
    payload = []
    if system_prompt:
        payload.append({"role": "system", "content": system_prompt})
    payload.extend(messages)

    max_retries = 3

    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model=config.ACTIVE_MODEL,
                messages=payload,
                temperature=0.85,
                max_tokens=220,
                timeout=20.0
            )
            
            content = response.choices[0].message.content
            
            # Check if OpenRouter gave us a valid response and strip out any reasoning model <think> blocks
            if content and content.strip():
                cleaned_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                if cleaned_content:
                    return cleaned_content
                
            logger.warning(f"Attempt {attempt + 1}: Received blank text from API.")
            
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} API Error: {e}")
            
        if attempt < max_retries - 1:
            await asyncio.sleep(1.5 * (attempt + 1))
            
    return IN_CHARACTER_FALLBACKS[0]