import asyncio
import base64
import json
import re
import urllib.parse
import urllib.request


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _amount_found(text: str, amount: float) -> bool:
    target = round(float(amount), 2)
    for raw in re.findall(r"\d+(?:[,.]\d{1,2})?", text):
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        if round(value, 2) == target:
            return True
    return False


def _txid_found(text: str, txid: str) -> bool:
    normalized_text = _normalize(text)
    normalized_txid = _normalize(txid)
    if not normalized_txid:
        return False
    if normalized_txid in normalized_text:
        return True
    return len(normalized_txid) >= 8 and normalized_txid[-6:] in normalized_text


def _ocr_space_request(image_bytes: bytes, api_key: str, api_url: str) -> str:
    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    form = urllib.parse.urlencode(
        {
            "base64Image": f"data:image/jpeg;base64,{encoded_image}",
            "language": "eng",
            "isOverlayRequired": "false",
            "scale": "true",
            "OCREngine": "2",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        api_url,
        data=form,
        headers={
            "apikey": api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8", errors="ignore"))

    if payload.get("IsErroredOnProcessing"):
        errors = payload.get("ErrorMessage") or payload.get("ErrorDetails") or "OCR processing failed."
        if isinstance(errors, list):
            errors = "; ".join(str(item) for item in errors)
        raise ValueError(str(errors))

    parsed = payload.get("ParsedResults") or []
    return "\n".join(str(item.get("ParsedText", "")) for item in parsed).strip()


async def analyze_payment_screenshot(
    image_bytes: bytes,
    amount: float,
    txid: str,
    api_key: str,
    api_url: str,
    enabled: bool = True,
) -> tuple[str, str]:
    if not enabled:
        return "OCR disabled", "OCR is disabled in settings."
    if not api_key:
        return "OCR not configured", "OCR API key is missing."

    try:
        text = await asyncio.to_thread(_ocr_space_request, image_bytes, api_key, api_url)
    except Exception as exc:
        return "OCR failed", f"OCR failed: {exc}"

    amount_match = _amount_found(text, amount)
    txid_match = _txid_found(text, txid)
    if amount_match and txid_match:
        status = "OCR MATCHED"
    elif amount_match or txid_match:
        status = "OCR PARTIAL MATCH"
    else:
        status = "OCR NOT MATCHED"

    preview = text[:700].strip() or "No text detected."
    details = (
        f"{status}\n"
        f"Amount match: {'YES' if amount_match else 'NO'}\n"
        f"TXID match: {'YES' if txid_match else 'NO'}\n\n"
        f"OCR Text Preview:\n{preview}"
    )
    return status, details
