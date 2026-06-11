from bot.config import get_settings


def money(amount: float) -> str:
    settings = get_settings()
    symbol = settings.currency_symbol.strip()
    if symbol.upper() in {"TK", "BDT"} or symbol in {"৳", "à§³"}:
        return f"{float(amount):,.2f} TK"
    return f"{symbol}{float(amount):,.2f}"


def clean_support_username(username: str) -> str:
    return username[1:] if username.startswith("@") else username
