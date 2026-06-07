from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.keyboards.user import back_menu, deposit_methods, main_menu
from bot.services.coupons import redeem_coupon
from bot.services.deposits import create_deposit
from bot.services.orders import order_count, purchase_product, recent_orders
from bot.services.products import list_active_products
from bot.services.users import get_or_create_user, get_user_by_telegram_id
from bot.utils.formatting import clean_support_username, money

router = Router()


class DepositForm(StatesGroup):
    amount = State()
    transaction_id = State()


class CouponForm(StatesGroup):
    code = State()


def product_keyboard(products: list[tuple[object, int]]) -> InlineKeyboardMarkup:
    rows = []
    for product, stock_count in products:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{product.name} - {money(product.price)} ({stock_count})",
                    callback_data=f"buy:{product.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="Back", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
        await callback.message.edit_text("Available Products", reply_markup=product_keyboard(product_rows))
    await callback.answer()


@router.callback_query(F.data.startswith("buy:"))
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
