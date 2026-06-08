import json
import re

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

AGENT_PROMPT = """
You are an AI agent inside a Telegram digital shop bot.
Understand Bangla, English, Banglish, typo, broken spelling, and short casual messages.
Decide what the user wants and return ONLY valid JSON.

Allowed actions:
- menu
- shop
- deposit
- profile
- orders
- deposit_status
- sell
- coupon
- referral
- support
- answer

Rules:
- Use an action when the user clearly wants a bot task, even with typo.
- Use "answer" for general questions, confusion, advice, or when you need to explain.
- Never approve payments, refund orders, add/remove balance, delete products, or claim admin actions are completed.
- For risky/admin actions, choose "support" or "answer" and explain to use Admin Panel.
- Reply in the user's language style. Prefer short Bangla/Banglish.

JSON schema:
{"action":"one_allowed_action","reply":"short helpful reply"}
"""


def _gemini_model_candidates(primary_model: str) -> list[str]:
    fallback_models = (
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
    )
    models = [primary_model]
    for model in fallback_models:
        if model not in models:
            models.append(model)
    return models


def _is_retryable_error(status: int, message: str) -> bool:
    lowered = message.lower()
    return status in {429, 503} or "high demand" in lowered or "overloaded" in lowered


def _gemini_url(model: str, api_key: str) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"


async def ask_gemini(user_text: str, user_context: str = "") -> str:
    settings = get_settings()
    if not settings.ai_enabled:
        return "AI Help is currently disabled."
    if settings.ai_provider.lower() != "gemini":
        return "AI provider is not configured for Gemini."
    if not settings.gemini_api_key:
        return "Gemini API key is missing. Please add GEMINI_API_KEY in Railway Variables."

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
    last_error = ""
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for model in _gemini_model_candidates(settings.gemini_model):
            async with session.post(_gemini_url(model, settings.gemini_api_key), json=payload) as response:
                data = await response.json(content_type=None)
                if response.status < 400:
                    break
                error = data.get("error", {}) if isinstance(data, dict) else {}
                message = error.get("message") or f"Gemini error {response.status}"
                last_error = message
                if _is_retryable_error(response.status, message):
                    continue
                return f"AI error: {message}"
        else:
            return "AI ekhon busy ache. Ektu pore abar try korun."

    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        return "AI did not return a readable answer. Please try again."

    text = "\n".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    return text or "AI did not return an answer. Please try again."


def _extract_json(text: str) -> dict[str, str] | None:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        cleaned = match.group(0)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        action_match = re.search(r'"action"\s*:\s*"([^"]+)"', cleaned, flags=re.IGNORECASE)
        if not action_match:
            return None
        reply_match = re.search(r'"reply"\s*:\s*"([^"]*)"', cleaned, flags=re.IGNORECASE | re.DOTALL)
        return {
            "action": action_match.group(1).strip().lower(),
            "reply": reply_match.group(1).strip() if reply_match else "",
        }
    if not isinstance(data, dict):
        return None
    return {
        "action": str(data.get("action", "answer")).strip().lower(),
        "reply": str(data.get("reply", "")).strip(),
    }


async def ask_gemini_agent(user_text: str, user_context: str = "") -> dict[str, str]:
    settings = get_settings()
    if not settings.ai_enabled or settings.ai_provider.lower() != "gemini" or not settings.gemini_api_key:
        return {
            "action": "answer",
            "reply": "AI properly configured na. Railway Variables-e GEMINI_API_KEY check korun.",
        }

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            f"{AGENT_PROMPT.strip()}\n\n"
                            f"Shop context:\n{user_context.strip()}\n\n"
                            f"User message:\n{user_text.strip()}"
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.15,
            "maxOutputTokens": 220,
        },
    }

    timeout = aiohttp.ClientTimeout(total=25)
    last_error = ""
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for model in _gemini_model_candidates(settings.gemini_model):
            async with session.post(_gemini_url(model, settings.gemini_api_key), json=payload) as response:
                data = await response.json(content_type=None)
                if response.status < 400:
                    break
                error = data.get("error", {}) if isinstance(data, dict) else {}
                message = error.get("message") or f"Gemini error {response.status}"
                last_error = message
                if _is_retryable_error(response.status, message):
                    continue
                return {"action": "answer", "reply": f"AI error: {message}"}
        else:
            return {
                "action": "answer",
                "reply": "AI ekhon busy ache. Ektu pore abar message korun, ba direct menu button use korun.",
            }

    try:
        parts = data["candidates"][0]["content"]["parts"]
        raw_text = "\n".join(part.get("text", "") for part in parts if isinstance(part, dict))
    except (KeyError, IndexError, TypeError):
        return {"action": "answer", "reply": "AI did not return a readable answer. Please try again."}

    parsed = _extract_json(raw_text)
    if parsed:
        allowed = {
            "menu",
            "shop",
            "deposit",
            "profile",
            "orders",
            "deposit_status",
            "sell",
            "coupon",
            "referral",
            "support",
            "answer",
        }
        if parsed["action"] not in allowed:
            parsed["action"] = "answer"
        if not parsed["reply"] and parsed["action"] == "answer":
            parsed["reply"] = "Bujhlam. Ami help kortesi."
        return parsed

    clean_text = raw_text.strip()
    if clean_text.startswith("{") and '"action"' in clean_text:
        return {"action": "answer", "reply": "Bujhlam. Arektu details bolen, ami help kortesi."}
    return {"action": "answer", "reply": clean_text or "Bujhlam. Arektu details bolen, ami help kortesi."}
