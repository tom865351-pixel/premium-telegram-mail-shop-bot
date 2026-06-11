from dataclasses import dataclass
from typing import Any

import aiohttp

from bot.config import get_settings


@dataclass(slots=True)
class ZiniPayResult:
    success: bool
    message: str
    provider: str | None = None
    sender_number: str | None = None
    raw: dict[str, Any] | None = None


def zinipay_ready() -> bool:
    settings = get_settings()
    return bool(settings.zinipay_trx_enabled and settings.zinipay_api_key)


async def _post(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    base_url = settings.zinipay_trx_base_url.rstrip("/")
    headers = {"zinipay-api-key": settings.zinipay_api_key or ""}
    timeout = aiohttp.ClientTimeout(total=25)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(f"{base_url}/{endpoint}", json=payload, headers=headers) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                message = data.get("message") if isinstance(data, dict) else None
                code = data.get("code") if isinstance(data, dict) else None
                detail = f"{message or 'ZiniPay request failed'}"
                if code:
                    detail = f"{detail} ({code})"
                raise RuntimeError(detail)
            return data


async def verify_and_confirm_transaction(transaction_id: str, amount: float) -> ZiniPayResult:
    if not zinipay_ready():
        return ZiniPayResult(False, "ZiniPay transaction verification is disabled.")

    normalized_amount = int(amount) if float(amount).is_integer() else float(amount)
    payload = {"transactionId": transaction_id.strip(), "amount": normalized_amount}
    try:
        verify_data = await _post("verify", payload)
        internal_id = verify_data.get("data", {}).get("id") if isinstance(verify_data, dict) else None
        if not internal_id:
            return ZiniPayResult(False, "ZiniPay verify response did not include transaction id.", raw=verify_data)

        confirm_data = await _post("confirm", {**payload, "id": internal_id})
        data = confirm_data.get("data", {}) if isinstance(confirm_data, dict) else {}
        return ZiniPayResult(
            success=True,
            message=confirm_data.get("message", "Transaction confirmed.") if isinstance(confirm_data, dict) else "Transaction confirmed.",
            provider=data.get("provider"),
            sender_number=data.get("senderNumber"),
            raw=confirm_data,
        )
    except Exception as exc:
        return ZiniPayResult(False, str(exc))
