import aiohttp

from bot.config import get_settings


SYSTEM_PROMPT = """
You are the AI help assistant for a Telegram digital shop bot.
Reply in short Bangla/Banglish unless the user writes in another language.
Help users with shop navigation, deposits, orders, coupons, referrals, support, and sell requests.
Do not claim you completed payments, refunds, balance changes, or admin actions.
If the user asks for a sensitive admin action, tell them to use the Admin Panel.
Keep answers practical and under 6 short lines.
"""


async def ask_gemini(user_text: str, user_context: str = "") -> str:
    settings = get_settings()
    if not settings.ai_enabled:
        return "AI Help is currently disabled."
    if settings.ai_provider.lower() != "gemini":
        return "AI provider is not configured for Gemini."
    if not settings.gemini_api_key:
        return "Gemini API key is missing. Please add GEMINI_API_KEY in Railway Variables."

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            f"{SYSTEM_PROMPT.strip()}\n\n"
                            f"Shop context:\n{user_context.strip()}\n\n"
                            f"User message:\n{user_text.strip()}"
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 300,
        },
    }

    timeout = aiohttp.ClientTimeout(total=25)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                error = data.get("error", {}) if isinstance(data, dict) else {}
                message = error.get("message") or f"Gemini error {response.status}"
                return f"AI error: {message}"

    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        return "AI did not return a readable answer. Please try again."

    text = "\n".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    return text or "AI did not return an answer. Please try again."
