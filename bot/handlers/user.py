import re
from io import BytesIO

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.keyboards.admin import admin_reply_menu, deposit_review_reply_menu, replacement_review_reply_menu
from bot.keyboards.user import deposit_methods_reply_menu, main_reply_menu, product_buy_reply_menu, products_reply_menu
from bot.services.coupons import redeem_coupon
from bot.database.models import DepositStatus, Order
from bot.services.ai import ask_gemini_agent
from bot.services.deposits import approved_deposit_count, create_deposit, deposited_today, recent_deposits, txid_exists
from bot.services.ocr import analyze_payment_screenshot
from bot.services.orders import order_count, purchase_product, purchase_product_bulk, recent_orders, spent_today, total_spent
from bot.services.products import list_active_products, unsold_stock_count
from bot.services.replacements import create_replacement_request, recent_replacements
from bot.services.users import get_or_create_user, get_user_by_telegram_id
from bot.utils.formatting import clean_support_username, money
from bot.utils.ui import panel

router = Router()

RESERVED_REPLY_TEXTS = {
    "🏠 Main Menu",
    "🏠 Menu",
    "MAIN MENU",
    "MENU",
    "Menu",
    "Main Menu",
    "🛍 Shop Now",
    "🛍 Shop",
    "MAIL SHOP",
    "Shop",
    "💼 Sell",
    "Sell",
    "🤖 AI",
    "AI",
    "AI Help",
    "💳 Deposit",
    "💳 Top Up",
    "Top Up",
    "ADD BALANCE",
    "Deposit",
    "👤 Profile",
    "MY PROFILE",
    "Profile",
    "🎁 Refer",
    "REFERRAL",
    "Referral",
    "🏷 Coupon",
    "COUPON",
    "Coupon",
    "📦 Orders",
    "MY ORDERS",
    "Orders",
    "☎️ Support",
    "SUPPORT",
    "Support",
    "⚙️ Admin Panel",
    "ADMIN PANEL",
    "Admin Panel",
    "📦 Products",
    "PRODUCTS",
    "Products",
    "➕ Add Product",
    "ADD PRODUCT",
    "Add Product",
    "📥 Add Stock",
    "ADD STOCK",
    "Add Stock",
    "💳 Deposits",
    "DEPOSITS",
    "Deposits",
    "🏷 Coupons",
    "COUPONS",
    "Coupons",
    "📊 Stats",
    "STATS",
    "Stats",
    "👥 Members",
    "Members",
    "📋 All Members",
    "All Members",
    "🔎 Search Member",
    "Search Member",
    "📣 Broadcast",
    "Broadcast",
    "📈 Reports",
    "Reports",
    "🧾 Deposit Status",
    "🧾 Status",
    "Status",
    "Deposit Status",
    "🔁 Replace",
    "Replace",
    "REPLACE",
    "Cancel",
    "CANCEL",
    "🛍 Shop",
    "💼 Sell",
    "💳 Top Up",
    "🤖 AI",
    "👤 Profile",
    "📦 Orders",
    "🏷 Coupon",
    "🎁 Refer",
    "🧾 Status",
    "☎️ Support",
    "⚙️ Admin Panel",
    "🟡 Binance",
    "🛒 Single",
    "📦 Bulk",
    "🏠 Menu",
    "🏠 Main Menu",
    "🟡 Binance",
    "Binance",
    "💵 USDT TRC20",
    "TRC20",
    "USDT TRC20",
    "💵 USDT BEP20",
    "BEP20",
    "USDT BEP20",
    "📱 bKash",
    "bKash",
    "📱 Nagad",
    "Nagad",
    "🚀 Rocket",
    "Rocket",
    "🛒 Single Buy",
    "🛒 Single",
    "Single",
    "BUY 1 ACCOUNT",
    "Single Buy",
    "📦 Bulk Buy",
    "📦 Bulk",
    "Bulk",
    "BULK BUY",
    "Bulk Buy",
}

DEPOSIT_METHOD_TEXTS = {
    "🟡 Binance": "binance",
    "🟡 Binance": "binance",
    "Binance": "binance",
    "💵 USDT TRC20": "usdt_trc20",
    "TRC20": "usdt_trc20",
    "USDT TRC20": "usdt_trc20",
    "💵 USDT BEP20": "usdt_bep20",
    "BEP20": "usdt_bep20",
    "USDT BEP20": "usdt_bep20",
    "📱 bKash": "bkash",
    "bKash": "bkash",
    "📱 Nagad": "nagad",
    "Nagad": "nagad",
    "🚀 Rocket": "rocket",
    "Rocket": "rocket",
}

DEPOSIT_METHOD_LABELS = {
    "binance": "Binance",
    "usdt_trc20": "USDT TRC20",
    "usdt_bep20": "USDT BEP20",
    "bkash": "bKash",
    "nagad": "Nagad",
    "rocket": "Rocket",
}

MENU_ALIASES = {
    "🏠 Main Menu": "Main Menu",
    "🏠 Menu": "Main Menu",
    "🛍 Shop": "Shop",
    "💼 Sell": "Sell",
    "🤖 AI": "AI",
    "💳 Top Up": "Deposit",
    "👤 Profile": "Profile",
    "📦 Orders": "Orders",
    "🧾 Status": "Deposit Status",
    "🎁 Refer": "Referral",
    "🏷 Coupon": "Coupon",
    "🔁 Replace": "Replace",
    "REPLACE": "Replace",
    "Cancel": "Cancel",
    "CANCEL": "Cancel",
    "☎️ Support": "Support",
    "⚙️ Admin Panel": "Admin Panel",
    "🏠 Main Menu": "Main Menu",
    "🏠 Menu": "Main Menu",
    "MAIN MENU": "Main Menu",
    "MENU": "Main Menu",
    "Menu": "Main Menu",
    "🛍 Shop Now": "Shop",
    "🛍 Shop": "Shop",
    "MAIL SHOP": "Shop",
    "💼 Sell": "Sell",
    "SELL": "Sell",
    "🤖 AI": "AI",
    "AI": "AI",
    "AI HELP": "AI",
    "💳 Deposit": "Deposit",
    "💳 Top Up": "Deposit",
    "TOP UP": "Deposit",
    "ADD BALANCE": "Deposit",
    "👤 Profile": "Profile",
    "MY PROFILE": "Profile",
    "📦 Orders": "Orders",
    "MY ORDERS": "Orders",
    "🧾 Status": "Deposit Status",
    "STATUS": "Deposit Status",
    "🧾 Deposit Status": "Deposit Status",
    "DEPOSIT STATUS": "Deposit Status",
    "🎁 Refer": "Referral",
    "REFERRAL": "Referral",
    "🏷 Coupon": "Coupon",
    "COUPON": "Coupon",
    "☎️ Support": "Support",
    "SUPPORT": "Support",
    "⚙️ Admin Panel": "Admin Panel",
    "ADMIN PANEL": "Admin Panel",
    "📦 Products": "Products",
    "PRODUCTS": "Products",
    "➕ Add Product": "Add Product",
    "ADD PRODUCT": "Add Product",
    "📥 Add Stock": "Add Stock",
    "ADD STOCK": "Add Stock",
    "💳 Deposits": "Deposits",
    "DEPOSITS": "Deposits",
    "🏷 Coupons": "Coupons",
    "COUPONS": "Coupons",
    "📊 Stats": "Stats",
    "STATS": "Stats",
}
ADMIN_MENU_TEXTS = {"Admin Panel", "Products", "Add Product", "Add Stock", "Deposits", "Coupons", "Stats", "Members"}
GLOBAL_MENU_TEXTS = {
    "🏠 Main Menu",
    "🏠 Menu",
    "🛍 Shop",
    "💼 Sell",
    "🤖 AI",
    "💳 Top Up",
    "👤 Profile",
    "📦 Orders",
    "🧾 Status",
    "🎁 Refer",
    "🏷 Coupon",
    "🔁 Replace",
    "Cancel",
    "☎️ Support",
    "⚙️ Admin Panel",
    "Main Menu",
    "Menu",
    "Shop",
    "Deposit",
    "Sell",
    "AI",
    "Profile",
    "Orders",
    "Deposit Status",
    "Referral",
    "Coupon",
    "Support",
    "Admin Panel",
    "MAIN MENU",
    "MENU",
    "MAIL SHOP",
    "ADD BALANCE",
    "MY PROFILE",
    "MY ORDERS",
    "REFERRAL",
    "COUPON",
    "SUPPORT",
    "ADMIN PANEL",
    "🏠 Main Menu",
    "🏠 Menu",
    "🛍 Shop Now",
    "🛍 Shop",
    "💼 Sell",
    "🤖 AI",
    "💳 Deposit",
    "💳 Top Up",
    "👤 Profile",
    "📦 Orders",
    "🧾 Status",
    "🧾 Deposit Status",
    "🎁 Refer",
    "🏷 Coupon",
    "☎️ Support",
    "⚙️ Admin Panel",
}

ADMIN_ACTION_PREFIXES = (
    "Product #",
    "Member #",
    "Add Stock #",
    "Edit Product #",
    "Add Balance #",
    "Remove Balance #",
    "Check Orders #",
    "Check Balance #",
    "Note Member #",
    "Refund Order #",
    "Confirm Refund Order #",
    "Ban Member #",
    "Unban Member #",
    "Restrict Member #",
    "Unrestrict Member #",
    "Enable Product #",
    "Disable Product #",
    "Delete Product #",
    "Confirm Delete Product #",
    "Cancel Product #",
    "Approve Deposit #",
    "Reject Deposit #",
)


class DepositForm(StatesGroup):
    amount = State()
    transaction_id = State()
    screenshot = State()


class CouponForm(StatesGroup):
    code = State()


class SellForm(StatesGroup):
    details = State()


class AIHelpForm(StatesGroup):
    message = State()


class BulkBuyForm(StatesGroup):
    quantity = State()


class ReplaceForm(StatesGroup):
    details = State()
    proof = State()


def build_bulk_delivery_file(stock_items: list[object]) -> BufferedInputFile:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Accounts"
    worksheet.append(["No", "Email/Username", "Password", "Full Account"])

    for index, item in enumerate(stock_items, start=1):
        payload = item.payload.strip()
        username, password = payload, ""
        if "|" in payload:
            parts = [part.strip() for part in payload.split("|")]
            username = parts[0]
            password = parts[1] if len(parts) > 1 else ""
        worksheet.append([index, username, password, payload])

    worksheet.column_dimensions["A"].width = 8
    worksheet.column_dimensions["B"].width = 36
    worksheet.column_dimensions["C"].width = 24
    worksheet.column_dimensions["D"].width = 56

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return BufferedInputFile(output.read(), filename="bulk_accounts.xlsx")


def user_label(user: object) -> str:
    username = f"@{user.username}" if getattr(user, "username", None) else "No username"
    name = getattr(user, "first_name", None) or "Unknown"
    return f"{name} ({username})"


def deposit_admin_text(
    deposit: object,
    user: object,
    auto_approved: bool = False,
    review_reason: str | None = None,
) -> str:
    method = DEPOSIT_METHOD_LABELS.get(deposit.method, deposit.method.upper())
    title = "Auto Approved Deposit" if auto_approved else "New Deposit Request"
    footer = (
        "Balance was added automatically by semi-auto rules."
        if auto_approved
        else "Please verify the payment before approving."
    )
    return (
        f"{title}\n\n"
        f"Request ID: #{deposit.id}\n"
        f"Amount: {money(deposit.amount)}\n"
        f"Method: {method}\n"
        f"Transaction ID: <code>{deposit.transaction_id}</code>\n\n"
        f"Screenshot: {'Attached below' if getattr(deposit, 'proof_file_id', None) else 'Not provided'}\n\n"
        "Customer\n"
        f"Name: {user.first_name or 'Unknown'}\n"
        f"Username: @{user.username if user.username else 'not_available'}\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n\n"
        f"Review Note: {review_reason or 'Trusted semi-auto rules passed'}\n\n"
        f"{footer}"
    )


def parse_replace_details(text: str | None) -> tuple[int | None, int, str] | None:
    if not text:
        return None
    parts = [part.strip() for part in text.split("|", 2)]
    if len(parts) < 3:
        return None
    if parts[0] in {"-", "0", "none", "None"}:
        order_id = None
    else:
        try:
            order_id = int(parts[0].lstrip("#"))
        except ValueError:
            return None
    try:
        quantity = int(parts[1])
    except ValueError:
        return None
    if quantity < 1 or not parts[2]:
        return None
    return order_id, quantity, parts[2]


def replacement_admin_text(request: object, user: object) -> str:
    username = f"@{user.username}" if getattr(user, "username", None) else "No username"
    return (
        "Replacement Request\n\n"
        f"Request ID: #{request.id}\n"
        f"User: {user.first_name or 'Unknown'} ({username})\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Order ID: #{request.order_id or 'Not given'}\n"
        f"Quantity: {request.quantity}\n"
        f"Status: {request.status.value}\n\n"
        f"Message:\n{request.message}\n\n"
        f"Proof: {'Attached/file below' if request.proof_file_id else 'Text attached'}"
    )


async def notify_replacement_admins(message: Message, request: object, user: object) -> None:
    text = replacement_admin_text(request, user)
    for admin_id in get_settings().admin_ids:
        try:
            if request.proof_file_id and request.proof_file_name:
                await message.bot.send_document(admin_id, request.proof_file_id, caption=f"Replacement proof for request #{request.id}")
            elif request.proof_file_id:
                await message.bot.send_photo(admin_id, request.proof_file_id, caption=f"Replacement proof for request #{request.id}")
            elif request.proof_text:
                await message.bot.send_message(admin_id, f"Replacement proof text #{request.id}:\n\n{request.proof_text[:3500]}")
            await message.bot.send_message(admin_id, text, reply_markup=replacement_review_reply_menu(request.id))
        except Exception:
            pass


def clean_button_text(text: str | None) -> str:
    prefixes = (
        "🛒 ",
        "🛍 ",
        "💼 ",
        "💳 ",
        "🤖 ",
        "👤 ",
        "📦 ",
        "🔁 ",
        "🏷 ",
        "🎁 ",
        "🧾 ",
        "☎️ ",
        "⚙️ ",
        "🏠 ",
        "🟡 ",
        "🛒 ",
        "📦 ",
        "🛍 ",
        "💳 ",
        "👤 ",
        "🎁 ",
        "🏷 ",
        "☎️ ",
        "⚙️ ",
        "🏠 ",
        "🟡 ",
        "💵 ",
        "📱 ",
        "🚀 ",
    )
    cleaned = (text or "").strip()
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix) :].strip()
                changed = True
    return cleaned


def is_admin_action_text(text: str) -> bool:
    cleaned = re.sub(r"^[^A-Za-z0-9#]+", "", clean_button_text(text)).strip()
    upper_cleaned = cleaned.upper()
    return any(
        cleaned.startswith(prefix) or upper_cleaned.startswith(prefix.upper())
        for prefix in ADMIN_ACTION_PREFIXES
    )


def account_block_text(user: object, action: str = "use this feature") -> str | None:
    if getattr(user, "is_banned", False):
        return "Your account is banned. Please contact support."
    if getattr(user, "is_restricted", False):
        return f"Your account is restricted. You cannot {action}. Please contact support."
    return None


def suspicious_txid_reason(txid: str) -> str | None:
    normalized = txid.strip().lower().replace(" ", "")
    suspicious_words = ("test", "fake", "demo", "txid", "trxid")
    suspicious_numbers = ("1234", "0000", "1111", "2222", "9999")
    if len(normalized) < 8:
        return "Transaction ID is too short for auto approval."
    if len(set(normalized)) <= 2:
        return "Transaction ID pattern looks suspicious."
    if any(word in normalized for word in suspicious_words):
        return "Transaction ID contains suspicious text."
    if any(number in normalized for number in suspicious_numbers):
        return "Transaction ID contains suspicious number pattern."
    return None


async def semi_auto_deposit_decision(
    session: AsyncSession,
    user: object,
    amount: float,
    txid: str,
) -> tuple[bool, str]:
    settings = get_settings()
    if not settings.semi_auto_deposit_enabled:
        return False, "Semi-auto deposit is disabled."
    if amount > settings.semi_auto_deposit_max_amount:
        return False, f"Amount is above auto limit: {money(settings.semi_auto_deposit_max_amount)}."

    suspicious_reason = suspicious_txid_reason(txid)
    if suspicious_reason:
        return False, suspicious_reason

    approved_count = await approved_deposit_count(session, user.id)
    required_count = settings.semi_auto_trusted_user_min_approved_deposits
    if approved_count < required_count:
        return False, "First deposit requires manual admin verification."

    today_total = await deposited_today(session, user.id)
    if today_total + amount > settings.semi_auto_daily_user_limit:
        return False, f"Daily auto limit exceeded: {money(settings.semi_auto_daily_user_limit)}."

    return True, "Trusted user, unique TXID, and amount limits matched."


async def notify_low_stock_if_needed(message: Message, session: AsyncSession, product_id: int, product_name: str) -> None:
    settings = get_settings()
    remaining = await unsold_stock_count(session, product_id)
    if remaining > settings.low_stock_alert_threshold:
        return
    for admin_id in settings.admin_ids:
        try:
            await message.bot.send_message(
                admin_id,
                "Low Stock Alert\n\n"
                f"Product: {product_name}\n"
                f"Remaining Stock: {remaining}",
            )
        except Exception:
            pass


async def profile_text(session: AsyncSession, user: object) -> str:
    username = f"@{user.username}" if user.username else "Not set"
    today_deposit = await deposited_today(session, user.id)
    today_spent = await spent_today(session, user.id)
    lifetime_spent = await total_spent(session, user.id)
    return (
        f"👤 Name: {user.first_name or 'Unknown'}\n"
        f"🆔 User ID: {user.telegram_id}\n"
        f"👤 Username: {username}\n"
        f"💰 Balance: {money(user.balance)}\n"
        f"💵 Deposited today: {money(today_deposit)}\n"
        f"🧾 Spent today: {money(today_spent)}\n"
        f"📦 Total spent: {money(lifetime_spent)}"
    )


def ai_reply_text(text: str) -> str:
    clean = text.strip() if text else "Bujhlam. Ar kichu bolen, ami help kortesi."
    if clean.startswith("🤖"):
        return clean
    return f"🤖 AI Agent\n\n{clean}"


async def answer_ai_intent(message: Message, session: AsyncSession, state: FSMContext, user: object, text: str) -> bool:
    lowered = text.lower()
    is_admin = message.from_user.id in get_settings().admin_ids

    if any(word in lowered for word in ("menu", "main", "home", "start", "মেনু")):
        await state.clear()
        await message.answer(await profile_text(session, user), reply_markup=main_reply_menu(is_admin))
        return True

    if any(word in lowered for word in ("shop", "product", "buy", "gmail", "mail", "stock", "দাম", "কিন")):
        product_rows = await list_active_products(session)
        if not product_rows:
            await message.answer("No products are available right now.", reply_markup=main_reply_menu(is_admin))
        else:
            await message.answer(
                panel("PRODUCT CATALOG", "Select a product from the keyboard below."),
                reply_markup=products_reply_menu(product_rows, is_admin),
            )
        return True

    if any(word in lowered for word in ("deposit", "top up", "payment", "add balance", "bkash", "nagad", "recharge", "টাকা")):
        await message.answer(
            panel("ADD BALANCE", "Select your preferred payment method from the keyboard below."),
            reply_markup=deposit_methods_reply_menu(),
        )
        return True

    if any(word in lowered for word in ("balance", "profile", "account", "amar taka", "ব্যালেন্স")):
        await message.answer(await profile_text(session, user), reply_markup=main_reply_menu(is_admin))
        return True

    if any(word in lowered for word in ("order", "history", "purchase", "invoice", "অর্ডার")):
        rows = await recent_orders(session, user.id)
        if not rows:
            response = "Order History\n\nNo orders found."
        else:
            response = "Recent Orders\n\n" + "\n".join(
                f"#{order.id} - {money(order.amount)} - {order.created_at:%Y-%m-%d %H:%M}" for order in rows
            )
        await message.answer(response, reply_markup=main_reply_menu(is_admin))
        return True

    if any(word in lowered for word in ("status", "deposit status", "pending", "approved")):
        rows = await recent_deposits(session, user.id)
        if not rows:
            response = "Deposit Status\n\nNo deposits found."
        else:
            response = "Deposit Status\n\n" + "\n".join(
                f"#{deposit.id} - {money(deposit.amount)} - {deposit.method.upper()} - {deposit.status.value}"
                for deposit in rows
            )
        await message.answer(response, reply_markup=main_reply_menu(is_admin))
        return True

    if any(word in lowered for word in ("sell", "sale", "offer", "বিক্রি")):
        await state.set_state(SellForm.details)
        await message.answer(
            "Sell Request\n\n"
            "Send what you want to sell in this format:\n\n"
            "Product type | Quantity | Expected price | Details"
        )
        return True

    if any(word in lowered for word in ("coupon", "code", "discount")):
        await state.set_state(CouponForm.code)
        await message.answer("Coupon Redemption\n\nSend your coupon code.")
        return True

    if any(word in lowered for word in ("refer", "referral", "commission")):
        bot_username = (await message.bot.me()).username
        link = f"https://t.me/{bot_username}?start={user.referral_code}"
        await message.answer(
            "Referral Program\n\n"
            f"Commission: {get_settings().referral_commission_percent}%\n"
            f"Your link:\n{link}",
            reply_markup=main_reply_menu(is_admin),
        )
        return True

    if any(word in lowered for word in ("support", "help", "admin", "contact", "সাপোর্ট")):
        username = clean_support_username(get_settings().support_username)
        await message.answer(f"Support: @{username}", reply_markup=main_reply_menu(is_admin))
        return True

    return False


async def execute_ai_action(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    user: object,
    action: str,
    reply: str,
    keep_ai_chat: bool = False,
) -> bool:
    settings = get_settings()
    is_admin = message.from_user.id in settings.admin_ids
    action = action.lower().strip()

    if action == "answer":
        if keep_ai_chat:
            await state.set_state(AIHelpForm.message)
        await message.answer(ai_reply_text(reply), reply_markup=main_reply_menu(is_admin))
        return True

    if action == "menu":
        await state.clear()
        await message.answer(await profile_text(session, user), reply_markup=main_reply_menu(is_admin))
        return True

    if action == "shop":
        await state.clear()
        product_rows = await list_active_products(session)
        if not product_rows:
            await message.answer("No products are available right now.", reply_markup=main_reply_menu(is_admin))
        else:
            await message.answer(
                ai_reply_text(reply or "Product list open kore dilam."),
                reply_markup=products_reply_menu(product_rows, is_admin),
            )
        return True

    if action == "deposit":
        await state.clear()
        await message.answer(
            ai_reply_text(reply or "Deposit method select korun."),
            reply_markup=deposit_methods_reply_menu(),
        )
        return True

    if action == "profile":
        if keep_ai_chat:
            await state.set_state(AIHelpForm.message)
        else:
            await state.clear()
        await message.answer(await profile_text(session, user), reply_markup=main_reply_menu(is_admin))
        return True

    if action == "orders":
        if keep_ai_chat:
            await state.set_state(AIHelpForm.message)
        else:
            await state.clear()
        rows = await recent_orders(session, user.id)
        if not rows:
            text = "Order History\n\nNo orders found."
        else:
            text = "Recent Orders\n\n" + "\n".join(
                f"#{order.id} - {money(order.amount)} - {order.created_at:%Y-%m-%d %H:%M}" for order in rows
            )
        await message.answer(text, reply_markup=main_reply_menu(is_admin))
        return True

    if action == "deposit_status":
        if keep_ai_chat:
            await state.set_state(AIHelpForm.message)
        else:
            await state.clear()
        rows = await recent_deposits(session, user.id)
        if not rows:
            text = "Deposit Status\n\nNo deposits found."
        else:
            text = "Deposit Status\n\n" + "\n".join(
                f"#{deposit.id} - {money(deposit.amount)} - {deposit.method.upper()} - {deposit.status.value}"
                for deposit in rows
            )
        await message.answer(text, reply_markup=main_reply_menu(is_admin))
        return True

    if action == "sell":
        await state.set_state(SellForm.details)
        await message.answer(
            ai_reply_text(
                reply
            or (
                "Sell request korte details pathan:\n\n"
                "Product type | Quantity | Expected price | Details"
            )
            )
        )
        return True

    if action == "coupon":
        await state.set_state(CouponForm.code)
        await message.answer(ai_reply_text(reply or "Coupon code pathan."))
        return True

    if action == "referral":
        if keep_ai_chat:
            await state.set_state(AIHelpForm.message)
        else:
            await state.clear()
        bot_username = (await message.bot.me()).username
        link = f"https://t.me/{bot_username}?start={user.referral_code}"
        await message.answer(
            "Referral Program\n\n"
            f"Commission: {settings.referral_commission_percent}%\n"
            f"Your link:\n{link}",
            reply_markup=main_reply_menu(is_admin),
        )
        return True

    if action == "support":
        if keep_ai_chat:
            await state.set_state(AIHelpForm.message)
        else:
            await state.clear()
        username = clean_support_username(settings.support_username)
        await message.answer(ai_reply_text(reply or f"Support: @{username}"), reply_markup=main_reply_menu(is_admin))
        return True

    return False


async def send_menu(message: Message, session: AsyncSession, referral_code: str | None = None) -> None:
    settings = get_settings()
    user = await get_or_create_user(session, message.from_user, referral_code)
    if user.is_banned and message.from_user.id not in settings.admin_ids:
        await message.answer("Your account is banned. Please contact support.")
        return
    text = await profile_text(session, user)
    await message.answer(text, reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids))


async def send_deposit_for_insufficient_balance(message: Message, needed_amount: float, current_balance: float) -> None:
    await message.answer(
        "Insufficient Balance\n\n"
        f"Required: {money(needed_amount)}\n"
        f"Your Balance: {money(current_balance)}\n"
        f"Need More: {money(max(needed_amount - current_balance, 0))}\n\n"
        "Please top up first. Select a payment method below.",
        reply_markup=deposit_methods_reply_menu(),
    )


@router.message(Command("start"))
async def start(message: Message, command: CommandObject, session: AsyncSession) -> None:
    await send_menu(message, session, command.args)


@router.message(StateFilter("*"), F.text.in_(GLOBAL_MENU_TEXTS))
async def global_menu_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    settings = get_settings()
    user = await get_or_create_user(session, message.from_user)
    selected = MENU_ALIASES.get(message.text, message.text)
    if user.is_banned and message.from_user.id not in settings.admin_ids:
        await message.answer("Your account is banned. Please contact support.")
        return
    restricted_actions = {
        "Shop": "shop",
        "Sell": "sell accounts",
        "Deposit": "deposit",
        "Coupon": "redeem coupons",
        "Referral": "use referral",
        "Orders": "view orders",
    }
    if selected in restricted_actions:
        block_text = account_block_text(user, restricted_actions[selected])
        if block_text:
            await message.answer(block_text, reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids))
            return

    if selected == "Main Menu":
        await message.answer(
            panel("MAIN MENU", f"Balance: {money(user.balance)}", "", "Select an option from the keyboard."),
            reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids),
        )
        return

    if selected == "Cancel":
        await message.answer(
            "Current task cancelled.\n\nMain menu is ready.",
            reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids),
        )
        return

    if selected == "Shop":
        product_rows = await list_active_products(session)
        if not product_rows:
            await message.answer(
                "No products are available right now. Please check again later.",
                reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids),
            )
            return
        await message.answer(
            panel("PRODUCT CATALOG", "Select a product from the keyboard below."),
            reply_markup=products_reply_menu(product_rows, message.from_user.id in settings.admin_ids),
        )
        return

    if selected == "AI":
        await state.set_state(AIHelpForm.message)
        await message.answer(
            "🤖 AI Agent\n\n"
            "Bangla, English, Banglish, typo sob chole. Apni normal vabe bolun ki korte chan.\n\n"
            "Examples:\n"
            "- amar blance koto\n"
            "- diposit korta chai\n"
            "- gmail ache naki\n"
            "- order histry dao\n"
            "- sell korte chai\n\n"
            "Send Main Menu to exit."
        )
        return

    if selected == "Sell":
        await state.set_state(SellForm.details)
        await message.answer(
            "Sell Request\n\n"
            "Send what you want to sell in this format:\n\n"
            "Product type | Quantity | Expected price | Details\n\n"
            "Example:\n"
            "Gmail fresh | 20 | 10 TK each | old stock, recovery attached"
        )
        return

    if selected == "Replace":
        await state.set_state(ReplaceForm.details)
        await message.answer(
            "Replace Request\n\n"
            "Send details in this format:\n\n"
            "Order ID | Quantity | Problem message\n\n"
            "Example:\n"
            "12 | 5 | 5 mail login problem\n\n"
            "After this, send problem mail list as text or upload .txt/.csv/.xlsx/photo.",
        )
        return

    if selected == "Deposit":
        await message.answer(
            panel("ADD BALANCE", "Select your preferred payment method from the keyboard below."),
            reply_markup=deposit_methods_reply_menu(),
        )
        return

    if selected == "Profile":
        await message.answer(await profile_text(session, user), reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids))
        return

    if selected == "Orders":
        rows = await recent_orders(session, user.id)
        if not rows:
            text = "Order History\n\nNo orders found."
        else:
            text = "Recent Orders\n\n" + "\n".join(
                f"#{order.id} - {money(order.amount)} - {order.created_at:%Y-%m-%d %H:%M}" for order in rows
            )
        await message.answer(text, reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids))
        return

    if selected == "Deposit Status":
        rows = await recent_deposits(session, user.id)
        if not rows:
            text = "Deposit Status\n\nNo deposits found."
        else:
            text = "Deposit Status\n\n" + "\n".join(
                f"#{deposit.id} - {money(deposit.amount)} - {deposit.method.upper()} - {deposit.status.value}"
                for deposit in rows
            )
        await message.answer(text, reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids))
        return

    if selected == "Referral":
        bot_username = (await message.bot.me()).username
        link = f"https://t.me/{bot_username}?start={user.referral_code}"
        await message.answer(
            "Referral Program\n\n"
            f"Commission: {settings.referral_commission_percent}%\n"
            f"Your link:\n{link}",
            reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids),
        )
        return

    if selected == "Coupon":
        await state.set_state(CouponForm.code)
        await message.answer("Coupon Redemption\n\nSend your coupon code.")
        return

    if selected == "Support":
        username = clean_support_username(settings.support_username)
        await message.answer(f"Support: @{username}", reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids))
        return

    if selected == "Admin Panel":
        if message.from_user.id not in settings.admin_ids:
            await message.answer("You are not authorized.", reply_markup=main_reply_menu(False))
            return
        await message.answer(
            "Admin Panel\n\nManage products, stock, deposits, coupons, and store statistics.",
            reply_markup=admin_reply_menu(),
        )
        return



@router.callback_query(F.data == "menu")
async def menu(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    settings = get_settings()
    user = await get_or_create_user(session, callback.from_user)
    await callback.message.edit_text(
        "Main Menu\n\n"
        f"Balance: {money(user.balance)}\n"
        "Select an option from the keyboard.",
    )
    await callback.message.answer("Menu updated.", reply_markup=main_reply_menu(callback.from_user.id in settings.admin_ids))
    await callback.answer()


@router.message(StateFilter(None), F.text == "Main Menu")
async def menu_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    settings = get_settings()
    user = await get_or_create_user(session, message.from_user)
    await message.answer(
        f"Main Menu\n\nBalance: {money(user.balance)}",
        reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids),
    )


@router.callback_query(F.data == "dashboard")
async def dashboard(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, callback.from_user)
    await callback.message.edit_text(await profile_text(session, user))
    await callback.message.answer("Menu", reply_markup=main_reply_menu(callback.from_user.id in get_settings().admin_ids))
    await callback.answer()


@router.message(StateFilter(None), F.text == "Profile")
async def dashboard_text(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(session, message.from_user)
    await message.answer(await profile_text(session, user), reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids))


@router.callback_query(F.data == "products")
async def products(callback: CallbackQuery, session: AsyncSession) -> None:
    product_rows = await list_active_products(session)
    if not product_rows:
        await callback.message.edit_text("No products are available right now.")
        await callback.message.answer("Menu", reply_markup=main_reply_menu(callback.from_user.id in get_settings().admin_ids))
    else:
        await callback.message.answer(
            "Product Catalog\n\nSelect a product from the keyboard below.",
            reply_markup=products_reply_menu(product_rows, callback.from_user.id in get_settings().admin_ids),
        )
        await callback.message.edit_text("Products")
    await callback.answer()


@router.message(StateFilter(None), F.text == "Shop")
async def products_text(message: Message, session: AsyncSession) -> None:
    product_rows = await list_active_products(session)
    if not product_rows:
        await message.answer(
            "No products are available right now. Please check again later.",
            reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids),
        )
        return
    await message.answer(
        "Product Catalog\n\nSelect a product from the keyboard below.",
        reply_markup=products_reply_menu(product_rows, message.from_user.id in get_settings().admin_ids),
    )


@router.callback_query(F.data.startswith("product:"))
async def product_detail(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    product_id = int(callback.data.split(":", 1)[1])
    product_rows = await list_active_products(session)
    product_row = next((row for row in product_rows if row[0].id == product_id), None)
    if not product_row:
        await callback.answer("Product is unavailable.", show_alert=True)
        return

    product, stock_count = product_row
    await state.update_data(selected_product_id=product.id)
    await callback.message.edit_text(
        f"Product Details\n\n"
        f"Name: {product.name}\n"
        f"Price: {money(product.price)}\n"
        f"Available Stock: {stock_count}\n\n"
        f"Description: {product.description or 'No description provided.'}",
    )
    await callback.message.answer(
        "Select purchase type from the keyboard below.",
        reply_markup=product_buy_reply_menu(callback.from_user.id in get_settings().admin_ids),
    )
    await callback.answer()


async def send_product_detail_message(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    product_name: str,
) -> bool:
    user = await get_or_create_user(session, message.from_user)
    block_text = account_block_text(user, "shop")
    if block_text:
        await message.answer(block_text, reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids))
        return True

    product_name = clean_button_text(product_name)
    product_rows = await list_active_products(session)
    product_row = next((row for row in product_rows if row[0].name.lower() == product_name.lower()), None)
    if not product_row:
        return False

    product, stock_count = product_row
    await state.update_data(selected_product_id=product.id)
    await message.answer(
        f"{product.name}\n\n"
        f"Price: {money(product.price)}\n"
        f"File Stock: {stock_count}\n\n"
        f"{product.description or 'Select single buy or bulk buy.'}",
        reply_markup=product_buy_reply_menu(message.from_user.id in get_settings().admin_ids),
    )
    return True


@router.callback_query(F.data.startswith("buy_one:"))
async def buy_product(callback: CallbackQuery, session: AsyncSession) -> None:
    product_id = int(callback.data.split(":", 1)[1])
    user = await get_or_create_user(session, callback.from_user)
    ok, message, stock_item = await purchase_product(session, user, product_id)
    if not ok:
        if message.startswith("Insufficient balance"):
            product_rows = await list_active_products(session)
            product_row = next((row for row in product_rows if row[0].id == product_id), None)
            needed = float(product_row[0].price) if product_row else 0.0
            await callback.message.answer(
                "Insufficient Balance\n\n"
                f"Required: {money(needed)}\n"
                f"Your Balance: {money(user.balance)}\n\n"
                "Please top up first. Select a payment method below.",
                reply_markup=deposit_methods_reply_menu(),
            )
            await callback.answer()
            return
        await callback.answer(message, show_alert=True)
        return

    await callback.message.answer(
        "Order Invoice\n\n"
        f"Order ID: #{stock_item.sold_order_id}\n"
        f"Product ID: #{product_id}\n"
        "Status: completed\n\n"
        "Delivered Account:\n"
        f"<code>{stock_item.payload}</code>",
    )
    await notify_low_stock_if_needed(callback.message, session, product_id, f"#{product_id}")
    await callback.answer("Delivered.")


@router.message(StateFilter(None), F.text.in_({"Single", "Single Buy", "BUY 1 ACCOUNT", "🛒 Single", "🛒 Single Buy"}))
async def buy_product_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    product_id = data.get("selected_product_id")
    if not product_id:
        await message.answer("Please select a product first.", reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids))
        return

    user = await get_or_create_user(session, message.from_user)
    product_rows = await list_active_products(session)
    product_row = next((row for row in product_rows if row[0].id == int(product_id)), None)
    product_name = product_row[0].name if product_row else f"#{product_id}"
    ok, text, stock_item = await purchase_product(session, user, int(product_id))
    if not ok:
        if text.startswith("Insufficient balance") and product_row:
            await state.clear()
            await send_deposit_for_insufficient_balance(message, float(product_row[0].price), float(user.balance))
            return
        await message.answer(f"Purchase failed\n\n{text}", reply_markup=product_buy_reply_menu(message.from_user.id in get_settings().admin_ids))
        return

    await state.clear()
    await message.answer(
        "Order Invoice\n\n"
        f"Order ID: #{stock_item.sold_order_id}\n"
        f"Product: {product_name}\n"
        f"Price: {money(product_row[0].price) if product_row else 'N/A'}\n"
        "Status: completed\n\n"
        "Delivered Account:\n"
        f"<code>{stock_item.payload}</code>",
        reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids),
    )
    await notify_low_stock_if_needed(message, session, int(product_id), product_name)


@router.message(StateFilter("*"), F.text == "🛒 Single")
async def buy_product_text_current_keyboard(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await buy_product_text(message, state, session)


@router.callback_query(F.data.startswith("bulk_buy:"))
async def bulk_buy_start(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":", 1)[1])
    await state.update_data(product_id=product_id)
    await state.set_state(BulkBuyForm.quantity)
    await callback.message.edit_text("Enter bulk quantity.\n\nMinimum quantity: 2")
    await callback.answer()


@router.message(StateFilter(None), F.text.in_({"Bulk", "Bulk Buy", "BULK BUY", "📦 Bulk", "📦 Bulk Buy"}))
async def bulk_buy_start_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    product_id = data.get("selected_product_id")
    if not product_id:
        await message.answer("Please select a product first.", reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids))
        return
    await state.update_data(product_id=product_id)
    await state.set_state(BulkBuyForm.quantity)
    await message.answer("Enter bulk quantity.\n\nMinimum quantity: 2")


@router.message(StateFilter("*"), F.text == "📦 Bulk")
async def bulk_buy_start_text_current_keyboard(message: Message, state: FSMContext) -> None:
    await bulk_buy_start_text(message, state)


@router.message(BulkBuyForm.quantity)
async def bulk_buy_finish(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        quantity = int(message.text)
    except (TypeError, ValueError):
        await message.answer("Please enter a valid whole number, for example: 5")
        return

    data = await state.get_data()
    user = await get_or_create_user(session, message.from_user)
    product_rows = await list_active_products(session)
    product_row = next((row for row in product_rows if row[0].id == int(data["product_id"])), None)
    product_name = product_row[0].name if product_row else f"#{data['product_id']}"
    ok, text, stock_items = await purchase_product_bulk(session, user, int(data["product_id"]), quantity)
    if not ok:
        if text.startswith("Insufficient balance") and product_row:
            total_price = round(float(product_row[0].price) * quantity, 2)
            await state.clear()
            await send_deposit_for_insufficient_balance(message, total_price, float(user.balance))
            return
        await message.answer(text)
        return

    await state.clear()
    delivery_file = build_bulk_delivery_file(stock_items)
    await message.answer_document(
        delivery_file,
        caption=(
            "Bulk Order Invoice\n\n"
            f"Product: {product_name}\n"
            f"Quantity: {len(stock_items)}\n"
            f"Status: completed\n\n"
            f"{text}\n\nDelivered {len(stock_items)} account(s) in an Excel file."
        ),
        reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids),
    )
    await notify_low_stock_if_needed(message, session, int(data["product_id"]), product_name)


@router.callback_query(F.data == "orders")
async def orders(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, callback.from_user)
    rows = await recent_orders(session, user.id)
    if not rows:
        text = "Order History\n\nNo orders found."
    else:
        text = "Recent Orders\n\n" + "\n".join(
            f"#{order.id} - {money(order.amount)} - {order.created_at:%Y-%m-%d %H:%M}" for order in rows
        )
    await callback.message.edit_text(text)
    await callback.message.answer("Menu", reply_markup=main_reply_menu(callback.from_user.id in get_settings().admin_ids))
    await callback.answer()


@router.message(StateFilter(None), F.text == "Orders")
async def orders_text(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(session, message.from_user)
    rows = await recent_orders(session, user.id)
    if not rows:
        text = "Order History\n\nNo orders found."
    else:
        text = "Recent Orders\n\n" + "\n".join(
            f"#{order.id} - {money(order.amount)} - {order.created_at:%Y-%m-%d %H:%M}" for order in rows
        )
    await message.answer(text, reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids))


@router.message(StateFilter("*"), F.text.in_({"Status", "🧾 Status", "Deposit Status", "🧾 Deposit Status"}))
async def deposit_status_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    user = await get_or_create_user(session, message.from_user)
    rows = await recent_deposits(session, user.id, limit=10)
    if not rows:
        text = "Deposit Status\n\nNo deposits found."
    else:
        text = "Deposit Status\n\n" + "\n".join(
            f"#{deposit.id} - {money(deposit.amount)} - {deposit.method.upper()} - {deposit.status.value}"
            for deposit in rows
        )
    await message.answer(text, reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids))


@router.message(ReplaceForm.details)
async def replace_details(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await get_or_create_user(session, message.from_user)
    block_text = account_block_text(user, "request replacement")
    if block_text:
        await state.clear()
        await message.answer(block_text, reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids))
        return
    parsed = parse_replace_details(message.text)
    if not parsed:
        await message.answer(
            "Invalid format.\n\n"
            "Use:\n"
            "Order ID | Quantity | Problem message\n\n"
            "Example:\n"
            "12 | 5 | 5 mail login problem\n\n"
            "Send Cancel to stop."
        )
        return
    order_id, quantity, problem = parsed
    if order_id:
        order = await session.get(Order, order_id)
        if not order or order.user_id != user.id:
            await message.answer("Order not found for your account. Please check the order ID or send 0 if you do not know it.")
            return
    await state.update_data(order_id=order_id, quantity=quantity, problem=problem)
    await state.set_state(ReplaceForm.proof)
    await message.answer(
        "Now send the problem accounts.\n\n"
        "You can send:\n"
        "- text list\n"
        "- .txt / .csv / .xlsx file\n"
        "- photo/screenshot\n\n"
        "Admin will check and approve the replacement/refund."
    )


async def _create_replace_from_proof(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    proof_text: str | None = None,
    proof_file_id: str | None = None,
    proof_file_name: str | None = None,
) -> None:
    data = await state.get_data()
    if not {"quantity", "problem"}.issubset(data):
        await state.clear()
        await message.answer(
            "Replacement session expired. Please start again from Replace.",
            reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids),
        )
        return
    user = await get_or_create_user(session, message.from_user)
    request = await create_replacement_request(
        session=session,
        user_id=user.id,
        order_id=data.get("order_id"),
        quantity=int(data["quantity"]),
        message=str(data["problem"]),
        proof_text=proof_text,
        proof_file_id=proof_file_id,
        proof_file_name=proof_file_name,
    )
    await state.clear()
    await notify_replacement_admins(message, request, user)
    await message.answer(
        "Replace Request Submitted\n\n"
        f"Request ID: #{request.id}\n"
        f"Order ID: #{request.order_id or 'Not given'}\n"
        f"Quantity: {request.quantity}\n\n"
        "Admin will check your proof. If approved, the replacement amount will be added to your balance.",
        reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids),
    )


@router.message(ReplaceForm.proof, F.document)
async def replace_proof_document(message: Message, state: FSMContext, session: AsyncSession) -> None:
    document = message.document
    await _create_replace_from_proof(
        message,
        state,
        session,
        proof_file_id=document.file_id,
        proof_file_name=document.file_name or "replacement_proof",
    )


@router.message(ReplaceForm.proof, F.photo)
async def replace_proof_photo(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _create_replace_from_proof(message, state, session, proof_file_id=message.photo[-1].file_id)


@router.message(ReplaceForm.proof)
async def replace_proof_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.text:
        await message.answer("Please send text, photo, or a .txt/.csv/.xlsx file.")
        return
    await _create_replace_from_proof(message, state, session, proof_text=message.text)


@router.callback_query(F.data == "deposit")
async def deposit(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Deposit Funds\n\nSelect your preferred payment method.")
    await callback.message.answer("Payment methods", reply_markup=deposit_methods_reply_menu())
    await callback.answer()


@router.message(StateFilter(None), F.text == "Deposit")
async def deposit_text(message: Message) -> None:
    await message.answer(
        "Deposit Funds\n\nSelect your preferred payment method from the keyboard below.",
        reply_markup=deposit_methods_reply_menu(),
    )


@router.callback_query(F.data.startswith("deposit_method:"))
async def deposit_method(callback: CallbackQuery, state: FSMContext) -> None:
    method = callback.data.split(":", 1)[1]
    await state.update_data(method=method)
    await state.set_state(DepositForm.amount)
    await callback.message.edit_text("Enter deposit amount.")
    await callback.answer()


@router.message(StateFilter(None), F.text.in_(DEPOSIT_METHOD_TEXTS.keys()))
async def deposit_method_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await get_or_create_user(session, message.from_user)
    block_text = account_block_text(user, "deposit")
    if block_text:
        await message.answer(block_text, reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids))
        return
    method = DEPOSIT_METHOD_TEXTS[message.text]
    await state.update_data(method=method)
    await state.set_state(DepositForm.amount)
    await message.answer(
        f"Payment Method: {DEPOSIT_METHOD_LABELS[method]}\n\n"
        "Enter the amount you want to deposit."
    )


@router.message(StateFilter("*"), F.text.in_(DEPOSIT_METHOD_TEXTS.keys()))
async def deposit_method_text_interrupt(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    await deposit_method_text(message, state, session)


@router.message(DepositForm.amount)
async def deposit_amount(message: Message, state: FSMContext) -> None:
    settings = get_settings()
    try:
        amount = float(message.text)
    except (TypeError, ValueError):
        await message.answer("Please enter a valid numeric amount.")
        return
    if amount < settings.min_deposit:
        await message.answer(f"Minimum deposit amount is {money(settings.min_deposit)}.")
        return

    data = await state.get_data()
    method = data["method"]
    payment_info = {
        "binance": settings.binance_pay_id,
        "usdt_trc20": settings.usdt_trc20_address,
        "usdt_bep20": settings.usdt_bep20_address,
        "bkash": settings.bkash_number,
        "nagad": settings.nagad_number,
        "rocket": settings.rocket_number,
    }.get(method)

    await state.update_data(amount=amount)
    await state.set_state(DepositForm.transaction_id)
    await message.answer(
        "Payment Instructions\n\n"
        f"Amount: {money(amount)}\n"
        f"Method: {DEPOSIT_METHOD_LABELS.get(method, method.upper())}\n"
        f"Payment Number/Address: <code>{payment_info or 'Contact support for payment details'}</code>\n\n"
        "After sending payment, reply with your transaction ID/reference."
    )


@router.message(DepositForm.transaction_id)
async def deposit_transaction(message: Message, state: FSMContext, session: AsyncSession) -> None:
    txid = message.text.strip()
    if len(txid) < 4:
        await message.answer("Transaction ID is too short. Please send a valid transaction ID/reference.")
        return
    if await txid_exists(session, txid):
        await state.clear()
        await message.answer(
            "Duplicate Transaction ID\n\n"
            "This transaction ID has already been submitted. If this is a mistake, please contact support.",
            reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids),
        )
        return

    await state.update_data(transaction_id=txid)
    await state.set_state(DepositForm.screenshot)
    await message.answer(
        "Payment Screenshot Required\n\n"
        "Now upload the payment screenshot.\n\n"
        "Admin will match your amount, transaction ID, and screenshot before approval."
    )


async def _process_deposit_screenshot(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.photo:
        await message.answer("Please upload a payment screenshot as a photo.")
        return

    data = await state.get_data()
    required = {"amount", "transaction_id", "method"}
    if not required.issubset(data):
        await state.clear()
        await message.answer(
            "Payment screenshot received, but deposit session was not found.\n\n"
            "Please start again: Top Up > payment method > amount > TXID > screenshot.",
            reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids),
        )
        return

    await message.answer("Payment screenshot received.\n\nChecking and submitting your deposit request...")
    user = await get_or_create_user(session, message.from_user)
    settings = get_settings()
    amount = float(data["amount"])
    txid = data["transaction_id"]
    auto_approved, review_reason = await semi_auto_deposit_decision(session, user, amount, txid)
    if auto_approved:
        review_reason = f"{review_reason} Screenshot proof attached."
    else:
        review_reason = f"{review_reason} Screenshot proof attached for admin matching."
    proof_file_id = message.photo[-1].file_id
    screenshot_buffer = BytesIO()
    ocr_status = "OCR not checked"
    ocr_details = "OCR was not completed."
    try:
        await message.bot.download(message.photo[-1], destination=screenshot_buffer)
        ocr_status, ocr_details = await analyze_payment_screenshot(
            image_bytes=screenshot_buffer.getvalue(),
            amount=amount,
            txid=txid,
            api_key=settings.ocr_space_api_key,
            api_url=settings.ocr_space_api_url,
            enabled=settings.ocr_enabled,
        )
    except Exception as exc:
        ocr_status = "OCR failed"
        ocr_details = f"OCR failed: {exc}"
    review_reason = f"{review_reason}\n\nOCR Assistant: {ocr_status}\n{ocr_details}"
    deposit = await create_deposit(
        session=session,
        user_id=user.id,
        amount=amount,
        method=data["method"],
        transaction_id=txid,
        proof_file_id=proof_file_id,
        ocr_status=ocr_status,
        ocr_details=ocr_details,
        status=DepositStatus.APPROVED if auto_approved else DepositStatus.PENDING,
    )
    await state.clear()
    for admin_id in settings.admin_ids:
        try:
            admin_text = deposit_admin_text(deposit, user, auto_approved=auto_approved, review_reason=review_reason)
            await message.bot.send_photo(
                admin_id,
                photo=proof_file_id,
                caption=f"Payment screenshot for deposit #{deposit.id}",
            )
            await message.bot.send_message(
                admin_id,
                admin_text,
                reply_markup=None if auto_approved else deposit_review_reply_menu(deposit.id),
            )
        except Exception:
            try:
                await message.bot.send_message(
                    admin_id,
                    deposit_admin_text(deposit, user, auto_approved=auto_approved, review_reason=review_reason),
                    reply_markup=None if auto_approved else deposit_review_reply_menu(deposit.id),
                )
            except Exception:
                pass
    if auto_approved:
        await message.answer(
            "Deposit Approved\n\n"
            f"Request ID: #{deposit.id}\n"
            f"Amount: {money(deposit.amount)}\n"
            f"Method: {DEPOSIT_METHOD_LABELS.get(deposit.method, deposit.method.upper())}\n"
            f"Transaction ID: <code>{deposit.transaction_id}</code>\n\n"
            "Your balance has been updated automatically.",
            reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids),
        )
    else:
        await message.answer(
            "Deposit Request Submitted\n\n"
            f"Request ID: #{deposit.id}\n"
            f"Amount: {money(deposit.amount)}\n"
            f"Method: {DEPOSIT_METHOD_LABELS.get(deposit.method, deposit.method.upper())}\n\n"
            f"Review note: {review_reason}\n\n"
            "This deposit needs admin verification before balance is added.",
            reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids),
        )


@router.message(DepositForm.screenshot)
async def deposit_screenshot(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _process_deposit_screenshot(message, state, session)


@router.message(StateFilter("*"), F.photo)
async def photo_upload_fallback(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    current_state = await state.get_state()
    if current_state == DepositForm.screenshot.state or {"amount", "transaction_id", "method"}.issubset(data):
        await _process_deposit_screenshot(message, state, session)
        return
    await message.answer(
        "Photo received.\n\n"
        "If this is a payment screenshot, please start from Top Up and submit amount/TXID first.",
        reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids),
    )


@router.callback_query(F.data == "coupon")
async def coupon(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CouponForm.code)
    await callback.message.edit_text("Send your coupon code.")
    await callback.answer()


@router.message(StateFilter(None), F.text == "Coupon")
async def coupon_text(message: Message, state: FSMContext) -> None:
    await state.set_state(CouponForm.code)
    await message.answer("Coupon Redemption\n\nSend your coupon code.")


@router.message(CouponForm.code)
async def coupon_code(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await get_or_create_user(session, message.from_user)
    ok, text = await redeem_coupon(session, user, message.text)
    await state.clear()
    await message.answer(text, reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids))


@router.message(SellForm.details)
async def sell_request_finish(message: Message, state: FSMContext, session: AsyncSession) -> None:
    settings = get_settings()
    user = await get_or_create_user(session, message.from_user)
    block_text = account_block_text(user, "sell accounts")
    if block_text:
        await state.clear()
        await message.answer(block_text, reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids))
        return

    details = message.text.strip()
    if len(details) < 10:
        await message.answer(
            "Please send a little more detail.\n\n"
            "Format: Product type | Quantity | Expected price | Details"
        )
        return

    await state.clear()
    seller_username = f"@{message.from_user.username}" if message.from_user.username else "not_available"
    admin_text = (
        "New Sell Request\n\n"
        f"Seller: {message.from_user.full_name}\n"
        f"Username: {seller_username}\n"
        f"Telegram ID: <code>{message.from_user.id}</code>\n"
        f"Balance: {money(user.balance)}\n\n"
        "Offer Details:\n"
        f"{details}"
    )
    sent = 0
    for admin_id in settings.admin_ids:
        try:
            await message.bot.send_message(admin_id, admin_text)
            sent += 1
        except Exception:
            pass

    if sent:
        await message.answer(
            "Sell request submitted.\n\nAdmin will review your offer and contact you.",
            reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids),
        )
    else:
        await message.answer(
            "Sell request saved, but admin notification could not be sent. Please contact support.",
            reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids),
        )


@router.message(AIHelpForm.message)
async def ai_help_message(message: Message, state: FSMContext, session: AsyncSession) -> None:
    settings = get_settings()
    user = await get_or_create_user(session, message.from_user)
    if user.is_banned and message.from_user.id not in settings.admin_ids:
        await state.clear()
        await message.answer("Your account is banned. Please contact support.")
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Please send a text message.")
        return

    product_rows = await list_active_products(session)
    products = ", ".join(
        f"{product.name} ({money(product.price)}, stock {stock})" for product, stock in product_rows[:12]
    ) or "No products available"
    deposits = await recent_deposits(session, user.id, limit=3)
    recent_deposit_summary = ", ".join(
        f"#{deposit.id} {money(deposit.amount)} {deposit.status.value}" for deposit in deposits
    ) or "No recent deposits"
    user_context = (
        f"User name: {message.from_user.full_name}\n"
        f"User balance: {money(user.balance)}\n"
        f"Products: {products}\n"
        f"Recent deposits: {recent_deposit_summary}\n"
        f"Support username: @{clean_support_username(settings.support_username)}\n"
        "Available bot actions: menu, shop, deposit, profile, orders, deposit_status, sell, coupon, referral, support."
    )
    await message.answer("🤖 AI Agent is thinking...")
    agent = await ask_gemini_agent(text, user_context=user_context)
    handled = await execute_ai_action(
        message,
        session,
        state,
        user,
        agent.get("action", "answer"),
        agent.get("reply", ""),
        keep_ai_chat=True,
    )
    if not handled and not await answer_ai_intent(message, session, state, user, text):
        await message.answer(ai_reply_text(agent.get("reply") or "Bujhlam. Arektu details bolen."), reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids))


@router.callback_query(F.data == "referral")
async def referral(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, callback.from_user)
    bot_username = (await callback.bot.me()).username
    link = f"https://t.me/{bot_username}?start={user.referral_code}"
    await callback.message.edit_text(
        "Referral Program\n\n"
        f"Commission: {get_settings().referral_commission_percent}%\n"
        f"Your link:\n{link}",
    )
    await callback.message.answer("Menu", reply_markup=main_reply_menu(callback.from_user.id in get_settings().admin_ids))
    await callback.answer()


@router.message(StateFilter(None), F.text == "Referral")
async def referral_text(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(session, message.from_user)
    bot_username = (await message.bot.me()).username
    link = f"https://t.me/{bot_username}?start={user.referral_code}"
    await message.answer(
        "Referral Program\n\n"
        f"Commission: {get_settings().referral_commission_percent}%\n"
        f"Your link:\n{link}",
        reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids),
    )


@router.callback_query(F.data == "support")
async def support(callback: CallbackQuery) -> None:
    username = clean_support_username(get_settings().support_username)
    await callback.message.edit_text(f"Support: @{username}")
    await callback.message.answer("Menu", reply_markup=main_reply_menu(callback.from_user.id in get_settings().admin_ids))
    await callback.answer()


@router.message(StateFilter(None), F.text == "Support")
async def support_text(message: Message) -> None:
    username = clean_support_username(get_settings().support_username)
    await message.answer(f"Support: @{username}", reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids))


@router.message(Command("balance"))
async def balance(message: Message, session: AsyncSession) -> None:
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        user = await get_or_create_user(session, message.from_user)
    await message.answer(f"Balance: {money(user.balance)}")


@router.message(StateFilter("*"), F.document)
async def document_upload_fallback(message: Message, state: FSMContext, session: AsyncSession) -> None:
    from bot.handlers.admin import _process_stock_document, is_admin

    if is_admin(message.from_user.id):
        await _process_stock_document(message, state, session)
        return
    await message.answer(
        "File received.\n\n"
        "File upload is only available for admin stock upload right now.",
        reply_markup=main_reply_menu(False),
    )


@router.message(StateFilter(None), F.text.func(lambda text: text not in RESERVED_REPLY_TEXTS and not is_admin_action_text(text)))
async def product_name_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if await send_product_detail_message(message, session, state, message.text):
        return

    settings = get_settings()
    if not settings.ai_enabled:
        return

    user = await get_or_create_user(session, message.from_user)
    text = (message.text or "").strip()
    if not text:
        return

    product_rows = await list_active_products(session)
    products = ", ".join(
        f"{product.name} ({money(product.price)}, stock {stock})" for product, stock in product_rows[:12]
    ) or "No products available"
    user_context = (
        f"User name: {message.from_user.full_name}\n"
        f"User balance: {money(user.balance)}\n"
        f"Products: {products}\n"
        f"Support username: @{clean_support_username(settings.support_username)}\n"
        "The user sent a normal chat message outside AI mode. Be helpful and offer the right bot action."
    )
    await message.answer("🤖 AI Agent is thinking...")
    agent = await ask_gemini_agent(text, user_context=user_context)
    await execute_ai_action(
        message,
        session,
        state,
        user,
        agent.get("action", "answer"),
        agent.get("reply", ""),
        keep_ai_chat=True,
    )


@router.message(StateFilter("*"))
async def universal_message_fallback(message: Message, state: FSMContext, session: AsyncSession) -> None:
    from bot.handlers.admin import _process_stock_document, is_admin

    current_state = await state.get_state()
    data = await state.get_data()

    if message.document and is_admin(message.from_user.id):
        await _process_stock_document(message, state, session)
        return

    if message.photo:
        if current_state == DepositForm.screenshot.state or {"amount", "transaction_id", "method"}.issubset(data):
            await _process_deposit_screenshot(message, state, session)
            return
        await message.answer(
            "Photo peyechi.\n\n"
            "Payment screenshot submit korte hole age Top Up theke amount and TXID dite hobe.",
            reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids),
        )
        return

    if message.document:
        await message.answer(
            "File peyechi.\n\n"
            "Stock file upload only admin panel-er Add Stock flow theke kaj korbe.",
            reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids),
        )
        return

    if current_state:
        await message.answer(
            "Message peyechi, but ei step-e eta valid input na.\n\n"
            "Please button/menu follow korun, ba Main Menu press kore abar try korun.",
            reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids),
        )
        return

    await message.answer(
        "Message peyechi. Menu theke option select korun, ba 🤖 AI button use korun.",
        reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids),
    )
