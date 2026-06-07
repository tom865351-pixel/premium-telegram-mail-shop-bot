from bot.config import get_settings


def money(amount: float) -> str:
    settings = get_settings()
    return f"{settings.currency_symbol}{float(amount):.2f}"


def clean_support_username(username: str) -> str:
    return username[1:] if username.startswith("@") else username
