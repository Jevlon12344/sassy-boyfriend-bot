import aiohttp
import urllib.parse
import random
import logging
from aiogram.types import BufferedInputFile

logger = logging.getLogger(__name__)

async def generate_image(prompt: str) -> BufferedInputFile | None:
    """
    Downloads the image as bytes first so Telegram never times out.
    Uses a positive random seed.
    """
    try:
        encoded = urllib.parse.quote(prompt.strip())
        seed = random.randint(1, 999999)          # always positive
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?nologo=true&width=1024&height=1024&seed={seed}"
        )

        timeout = aiohttp.ClientTimeout(total=45)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    image_bytes = await resp.read()
                    return BufferedInputFile(image_bytes, filename="photo.jpg")
                logger.error(f"Pollinations status {resp.status}")
                return None
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        return None
