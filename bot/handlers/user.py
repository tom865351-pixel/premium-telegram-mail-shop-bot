from io import BytesIO

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.keyboards.admin import deposit_review_reply_menu
from bot.keyboards.user import deposit_methods_reply_menu, main_reply_menu, product_buy_reply_menu, products_reply_menu
from bot.services.coupons import redeem_coupon
from bot.services.deposits import create_deposit
from bot.services.orders import order_count, purchase_product, purchase_product_bulk, recent_orders
from bot.services.products import list_active_products
from bot.services.users import get_or_create_user, get_user_by_telegram_id
from bot.utils.formatting import clean_support_username, money

router = Router()

RESERVED_REPLY_TEXTS = {
    "Main Menu",
    "Shop",
    "Deposit",
    "Profile",
    "Referral",
    "Coupon",
    "Orders",
    "Support",
    "Admin Panel",
    "Products",
    "Add Product",
    "Add Stock",
    "Deposits",
    "Coupons",
    "Stats",
    "Binance",
    "USDT TRC20",
    "USDT BEP20",
    "bKash",
    "Nagad",
    "Rocket",
    "Single Buy",
    "Bulk Buy",
}

DEPOSIT_METHOD_TEXTS = {
    "Binance": "binance",
    "USDT TRC20": "usdt_trc20",
    "USDT BEP20": "usdt_bep20",
    "bKash": "bkash",
    "Nagad": "nagad",
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


class DepositForm(StatesGroup):
    amount = State()
    transaction_id = State()


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


def deposit_admin_text(deposit: object, user: object) -> str:
    method = DEPOSIT_METHOD_LABELS.get(deposit.method, deposit.method.upper())
    return (
        "New Deposit Request\n\n"
        f"Request ID: #{deposit.id}\n"
        f"Amount: {money(deposit.amount)}\n"
        f"Method: {method}\n"
        f"Transaction ID: <code>{deposit.transaction_id}</code>\n\n"
        "Customer\n"
        f"Name: {user.first_name or 'Unknown'}\n"
        f"Username: @{user.username if user.username else 'not_available'}\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n\n"
        "Please verify the payment before approving."
    )


async def send_menu(message: Message, session: AsyncSession, referral_code: str | None = None) -> None:
    settings = get_settings()
    user = await get_or_create_user(session, message.from_user, referral_code)
    text = (
        "Premium Mail Shop\n\n"
        f"Welcome, {user.first_name or 'Customer'}.\n"
        f"Current Balance: {money(user.balance)}\n\n"
        "Use the keyboard below to browse products, deposit funds, or manage your orders."
    )
    await message.answer(text, reply_markup=main_reply_menu(message.from_user.id in settings.admin_ids))


@router.message(Command("start"))
async def start(message: Message, command: CommandObject, session: AsyncSession) -> None:
    await send_menu(message, session, command.args)


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
    orders = await order_count(session, user.id)
    await callback.message.edit_text(
        "Account Profile\n\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Balance: {money(user.balance)}\n"
        f"Total Orders: {orders}\n"
        f"Referral Code: <code>{user.referral_code}</code>",
    )
    await callback.message.answer("Menu", reply_markup=main_reply_menu(callback.from_user.id in get_settings().admin_ids))
    await callback.answer()


@router.message(StateFilter(None), F.text == "Profile")
async def dashboard_text(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(session, message.from_user)
    orders = await order_count(session, user.id)
    await message.answer(
        "Account Profile\n\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Balance: {money(user.balance)}\n"
        f"Total Orders: {orders}\n"
        f"Referral Code: <code>{user.referral_code}</code>",
        reply_markup=main_reply_menu(message.from_user.id in get_settings().admin_ids),
    )


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


@router.message(StateFilter(None), F.text == "Single Buy")
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


@router.message(StateFilter(None), F.text == "Bulk Buy")
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
async def deposit_method_text(message: Message, state: FSMContext) -> None:
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
    data = await state.get_data()
    user = await get_or_create_user(session, message.from_user)
    deposit = await create_deposit(
        session=session,
        user_id=user.id,
        amount=float(data["amount"]),
        method=data["method"],
        transaction_id=message.text.strip(),
    )
    await state.clear()
    settings = get_settings()
    for admin_id in settings.admin_ids:
        try:
            await message.bot.send_message(
                admin_id,
                deposit_admin_text(deposit, user),
                reply_markup=deposit_review_reply_menu(deposit.id),
            )
        except Exception:
            pass
    await message.answer(
        "Deposit Request Submitted\n\n"
        f"Request ID: #{deposit.id}\n"
        f"Amount: {money(deposit.amount)}\n"
        f"Method: {DEPOSIT_METHOD_LABELS.get(deposit.method, deposit.method.upper())}\n\n"
        "Your request has been sent to admin for verification.",
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


@router.message(StateFilter(None), F.text.func(lambda text: text not in RESERVED_REPLY_TEXTS))
async def product_name_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await send_product_detail_message(message, session, state, message.text)
