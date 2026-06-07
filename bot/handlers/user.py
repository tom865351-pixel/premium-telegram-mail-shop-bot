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
from bot.keyboards.admin import admin_reply_menu, deposit_review_reply_menu
from bot.keyboards.user import deposit_methods_reply_menu, main_reply_menu, product_buy_reply_menu, products_reply_menu
from bot.services.coupons import redeem_coupon
from bot.database.models import DepositStatus
from bot.services.deposits import approved_deposit_count, create_deposit, deposited_today, txid_exists
from bot.services.orders import order_count, purchase_product, purchase_product_bulk, recent_orders, spent_today, total_spent
from bot.services.products import list_active_products
from bot.services.users import get_or_create_user, get_user_by_telegram_id
from bot.utils.formatting import clean_support_username, money
from bot.utils.ui import panel

router = Router()

RESERVED_REPLY_TEXTS = {
    "🏠 Main Menu",
    "MAIN MENU",
    "Main Menu",
    "🛍 Shop Now",
    "MAIL SHOP",
    "Shop",
    "💳 Deposit",
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
    "🟡 Binance",
    "Binance",
    "💵 USDT TRC20",
    "USDT TRC20",
    "💵 USDT BEP20",
    "USDT BEP20",
    "📱 bKash",
    "bKash",
    "📱 Nagad",
    "Nagad",
    "🚀 Rocket",
    "Rocket",
    "🛒 Single Buy",
    "BUY 1 ACCOUNT",
    "Single Buy",
    "📦 Bulk Buy",
    "BULK BUY",
    "Bulk Buy",
}

DEPOSIT_METHOD_TEXTS = {
    "🟡 Binance": "binance",
    "Binance": "binance",
    "💵 USDT TRC20": "usdt_trc20",
    "USDT TRC20": "usdt_trc20",
    "💵 USDT BEP20": "usdt_bep20",
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
    "MAIN MENU": "Main Menu",
    "🛍 Shop Now": "Shop",
    "MAIL SHOP": "Shop",
    "💳 Deposit": "Deposit",
    "ADD BALANCE": "Deposit",
    "👤 Profile": "Profile",
    "MY PROFILE": "Profile",
    "📦 Orders": "Orders",
    "MY ORDERS": "Orders",
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
    "Main Menu",
    "Shop",
    "Deposit",
    "Profile",
    "Orders",
    "Referral",
    "Coupon",
    "Support",
    "Admin Panel",
    "MAIN MENU",
    "MAIL SHOP",
    "ADD BALANCE",
    "MY PROFILE",
    "MY ORDERS",
    "REFERRAL",
    "COUPON",
    "SUPPORT",
    "ADMIN PANEL",
    "🏠 Main Menu",
    "🛍 Shop Now",
    "💳 Deposit",
    "👤 Profile",
    "📦 Orders",
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


class BulkBuyForm(StatesGroup):
    quantity = State()


def build_bulk_delivery_file(stock_items: list[object]) -> BufferedInputFile:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Accounts"
    worksheet.append(["No", "Email/Username", "Password", "Full Account"])

    for index, item in enumerate(stock_items, start=1):
        payload = item.payload.strip()
        username, password = payload, ""
        if "|" in payload:
            username, password = [part.strip() for part in payload.split("|", 1)]
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


def clean_button_text(text: str) -> str:
    prefixes = (
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
    cleaned = text.strip()
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


async def send_menu(message: Message, session: AsyncSession, referral_code: str | None = None) -> None:
    settings = get_settings()
    user = await get_or_create_user(session, message.from_user, referral_code)
    if user.is_banned and message.from_user.id not in settings.admin_ids:
        await message.answer("Your account is banned. Please contact support.")
        return
    text = await profile_text(session, user)
    await message.answer(text, reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids))


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
        await callback.answer(message, show_alert=True)
        return

    await callback.message.answer(
        "Order Completed\n\n"
        "Account details:\n"
        f"<code>{stock_item.payload}</code>",
    )
    await callback.answer("Delivered.")


@router.message(StateFilter(None), F.text.in_({"Single Buy", "BUY 1 ACCOUNT", "🛒 Single Buy"}))
async def buy_product_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    product_id = data.get("selected_product_id")
    if not product_id:
        await message.answer("Please select a product first.", reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids))
        return

    user = await get_or_create_user(session, message.from_user)
    ok, text, stock_item = await purchase_product(session, user, int(product_id))
    if not ok:
        await message.answer(f"Purchase failed\n\n{text}", reply_markup=product_buy_reply_menu(message.from_user.id in get_settings().admin_ids))
        return

    await message.answer(
        "Order Completed\n\n"
        "Account details:\n"
        f"<code>{stock_item.payload}</code>",
        reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids),
    )


@router.callback_query(F.data.startswith("bulk_buy:"))
async def bulk_buy_start(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":", 1)[1])
    await state.update_data(product_id=product_id)
    await state.set_state(BulkBuyForm.quantity)
    await callback.message.edit_text("Enter bulk quantity.\n\nMinimum quantity: 2")
    await callback.answer()


@router.message(StateFilter(None), F.text.in_({"Bulk Buy", "BULK BUY", "📦 Bulk Buy"}))
async def bulk_buy_start_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    product_id = data.get("selected_product_id")
    if not product_id:
        await message.answer("Please select a product first.", reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids))
        return
    await state.update_data(product_id=product_id)
    await state.set_state(BulkBuyForm.quantity)
    await message.answer("Enter bulk quantity.\n\nMinimum quantity: 2")


@router.message(BulkBuyForm.quantity)
async def bulk_buy_finish(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        quantity = int(message.text)
    except (TypeError, ValueError):
        await message.answer("Please enter a valid whole number, for example: 5")
        return

    data = await state.get_data()
    user = await get_or_create_user(session, message.from_user)
    ok, text, stock_items = await purchase_product_bulk(session, user, int(data["product_id"]), quantity)
    if not ok:
        await message.answer(text)
        return

    await state.clear()
    delivery_file = build_bulk_delivery_file(stock_items)
    await message.answer_document(
        delivery_file,
        caption=f"{text}\n\nDelivered {len(stock_items)} account(s) in an Excel file.",
        reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids),
    )


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


@router.message(DepositForm.screenshot)
async def deposit_screenshot(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.photo:
        await message.answer("Please upload a payment screenshot as a photo.")
        return

    data = await state.get_data()
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
    deposit = await create_deposit(
        session=session,
        user_id=user.id,
        amount=amount,
        method=data["method"],
        transaction_id=txid,
        proof_file_id=proof_file_id,
        status=DepositStatus.APPROVED if auto_approved else DepositStatus.PENDING,
    )
    await state.clear()
    for admin_id in settings.admin_ids:
        try:
            await message.bot.send_photo(
                admin_id,
                photo=proof_file_id,
                caption=deposit_admin_text(deposit, user, auto_approved=auto_approved, review_reason=review_reason),
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


@router.message(StateFilter(None), F.text.func(lambda text: text not in RESERVED_REPLY_TEXTS and not is_admin_action_text(text)))
async def product_name_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await send_product_detail_message(message, session, state, message.text)
