from io import BytesIO

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.keyboards.user import back_menu, deposit_methods, main_menu, product_buy_menu, products_menu
from bot.services.coupons import redeem_coupon
from bot.services.deposits import create_deposit
from bot.services.orders import order_count, purchase_product, purchase_product_bulk, recent_orders
from bot.services.products import list_active_products
from bot.services.users import get_or_create_user, get_user_by_telegram_id
from bot.utils.formatting import clean_support_username, money

router = Router()


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


async def send_menu(message: Message, session: AsyncSession, referral_code: str | None = None) -> None:
    settings = get_settings()
    user = await get_or_create_user(session, message.from_user, referral_code)
    text = (
        f"Welcome, {user.first_name or 'friend'}.\n\n"
        f"Balance: {money(user.balance)}\n"
        "Choose an option below."
    )
    await message.answer(text, reply_markup=main_menu(message.from_user.id in settings.admin_ids))


@router.message(Command("start"))
async def start(message: Message, command: CommandObject, session: AsyncSession) -> None:
    await send_menu(message, session, command.args)


@router.callback_query(F.data == "menu")
async def menu(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    settings = get_settings()
    user = await get_or_create_user(session, callback.from_user)
    await callback.message.edit_text(
        f"Main Menu\n\nBalance: {money(user.balance)}",
        reply_markup=main_menu(callback.from_user.id in settings.admin_ids),
    )
    await callback.answer()


@router.callback_query(F.data == "dashboard")
async def dashboard(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, callback.from_user)
    orders = await order_count(session, user.id)
    await callback.message.edit_text(
        "Dashboard\n\n"
        f"User ID: {user.telegram_id}\n"
        f"Balance: {money(user.balance)}\n"
        f"Total orders: {orders}\n"
        f"Referral code: {user.referral_code}",
        reply_markup=back_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "products")
async def products(callback: CallbackQuery, session: AsyncSession) -> None:
    product_rows = await list_active_products(session)
    if not product_rows:
        await callback.message.edit_text("No products available right now.", reply_markup=back_menu())
    else:
        await callback.message.edit_text("Choose a product.", reply_markup=products_menu(product_rows))
    await callback.answer()


@router.callback_query(F.data.startswith("product:"))
async def product_detail(callback: CallbackQuery, session: AsyncSession) -> None:
    product_id = int(callback.data.split(":", 1)[1])
    product_rows = await list_active_products(session)
    product_row = next((row for row in product_rows if row[0].id == product_id), None)
    if not product_row:
        await callback.answer("Product is unavailable.", show_alert=True)
        return

    product, stock_count = product_row
    await callback.message.edit_text(
        f"{product.name}\n\n"
        f"Price: {money(product.price)}\n"
        f"File Stock: {stock_count}\n\n"
        f"{product.description or 'Choose single buy or bulk buy.'}",
        reply_markup=product_buy_menu(product.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buy_one:"))
async def buy_product(callback: CallbackQuery, session: AsyncSession) -> None:
    product_id = int(callback.data.split(":", 1)[1])
    user = await get_or_create_user(session, callback.from_user)
    ok, message, stock_item = await purchase_product(session, user, product_id)
    if not ok:
        await callback.answer(message, show_alert=True)
        return

    await callback.message.answer(
        "Order completed.\n\n"
        "Your account details:\n"
        f"<code>{stock_item.payload}</code>",
    )
    await callback.answer("Delivered.")


@router.callback_query(F.data.startswith("bulk_buy:"))
async def bulk_buy_start(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":", 1)[1])
    await state.update_data(product_id=product_id)
    await state.set_state(BulkBuyForm.quantity)
    await callback.message.edit_text("Send bulk quantity. Minimum 2 items.", reply_markup=back_menu())
    await callback.answer()


@router.message(BulkBuyForm.quantity)
async def bulk_buy_finish(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        quantity = int(message.text)
    except (TypeError, ValueError):
        await message.answer("Send a whole number, for example 5.")
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
        caption=f"{text}\n\nDelivered {len(stock_items)} item(s) in Excel file.",
        reply_markup=main_menu(message.from_user.id in get_settings().admin_ids),
    )


@router.callback_query(F.data == "orders")
async def orders(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, callback.from_user)
    rows = await recent_orders(session, user.id)
    if not rows:
        text = "No orders yet."
    else:
        text = "Recent Orders\n\n" + "\n".join(
            f"#{order.id} - {money(order.amount)} - {order.created_at:%Y-%m-%d %H:%M}" for order in rows
        )
    await callback.message.edit_text(text, reply_markup=back_menu())
    await callback.answer()


@router.callback_query(F.data == "deposit")
async def deposit(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Choose a deposit method.", reply_markup=deposit_methods())
    await callback.answer()


@router.callback_query(F.data.startswith("deposit_method:"))
async def deposit_method(callback: CallbackQuery, state: FSMContext) -> None:
    method = callback.data.split(":", 1)[1]
    await state.update_data(method=method)
    await state.set_state(DepositForm.amount)
    await callback.message.edit_text("Enter deposit amount.", reply_markup=back_menu())
    await callback.answer()


@router.message(DepositForm.amount)
async def deposit_amount(message: Message, state: FSMContext) -> None:
    settings = get_settings()
    try:
        amount = float(message.text)
    except (TypeError, ValueError):
        await message.answer("Please enter a valid amount.")
        return
    if amount < settings.min_deposit:
        await message.answer(f"Minimum deposit is {money(settings.min_deposit)}.")
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
        f"Send {money(amount)} using {method.upper()}.\n"
        f"Payment address/number: <code>{payment_info or 'Ask support'}</code>\n\n"
        "After payment, send your transaction ID/reference."
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
    await message.answer(
        f"Deposit request #{deposit.id} submitted.\n"
        "An admin will review it shortly.",
        reply_markup=main_menu(message.from_user.id in get_settings().admin_ids),
    )


@router.callback_query(F.data == "coupon")
async def coupon(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CouponForm.code)
    await callback.message.edit_text("Send your coupon code.", reply_markup=back_menu())
    await callback.answer()


@router.message(CouponForm.code)
async def coupon_code(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await get_or_create_user(session, message.from_user)
    ok, text = await redeem_coupon(session, user, message.text)
    await state.clear()
    await message.answer(text, reply_markup=main_menu(message.from_user.id in get_settings().admin_ids))


@router.callback_query(F.data == "referral")
async def referral(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, callback.from_user)
    bot_username = (await callback.bot.me()).username
    link = f"https://t.me/{bot_username}?start={user.referral_code}"
    await callback.message.edit_text(
        "Referral Program\n\n"
        f"Commission: {get_settings().referral_commission_percent}%\n"
        f"Your link:\n{link}",
        reply_markup=back_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "support")
async def support(callback: CallbackQuery) -> None:
    username = clean_support_username(get_settings().support_username)
    await callback.message.edit_text(f"Support: @{username}", reply_markup=back_menu())
    await callback.answer()


@router.message(Command("balance"))
async def balance(message: Message, session: AsyncSession) -> None:
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        user = await get_or_create_user(session, message.from_user)
    await message.answer(f"Balance: {money(user.balance)}")
