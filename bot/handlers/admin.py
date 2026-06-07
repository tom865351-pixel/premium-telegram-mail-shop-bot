from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.keyboards.admin import admin_menu, admin_product_list, delete_product_confirm, deposit_review, product_admin_actions
from bot.keyboards.user import back_menu
from bot.services.coupons import create_coupon
from bot.services.deposits import pending_deposits, review_deposit
from bot.services.products import add_stock, create_product, delete_product, list_all_products, toggle_product
from bot.services.stats import admin_stats
from bot.utils.formatting import money

router = Router()


class ProductForm(StatesGroup):
    details = State()


class StockForm(StatesGroup):
    product_id = State()
    payload = State()


class CouponAdminForm(StatesGroup):
    details = State()


def is_admin(user_id: int) -> bool:
    return user_id in get_settings().admin_ids


@router.message(Command("admin"))
async def admin_command(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("You are not authorized.")
        return
    await message.answer("Admin Panel", reply_markup=admin_menu())


@router.callback_query(F.data == "admin")
async def admin_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    await callback.message.edit_text("Admin Panel", reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def stats(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    data = await admin_stats(session)
    await callback.message.edit_text(
        "Store Stats\n\n"
        f"Users: {data['users']}\n"
        f"Products: {data['products']}\n"
        f"Unsold stock: {data['stock']}\n"
        f"Orders: {data['orders']}\n"
        f"Revenue: {money(data['revenue'])}\n"
        f"Pending deposits: {data['pending_deposits']}",
        reply_markup=admin_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_products")
async def admin_products(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    rows = await list_all_products(session)
    if not rows:
        await callback.message.edit_text("No products created.", reply_markup=admin_menu())
    else:
        text = "Products\n\n" + "\n".join(
            f"#{product.id} {product.name} - {money(product.price)} - stock {stock} - {'active' if product.is_active else 'disabled'}"
            for product, stock in rows
        )
        await callback.message.edit_text(text, reply_markup=admin_product_list(rows))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_product:"))
async def admin_product_detail(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    product_id = int(callback.data.split(":", 1)[1])
    rows = await list_all_products(session)
    product_row = next((row for row in rows if row[0].id == product_id), None)
    if not product_row:
        await callback.answer("Product not found.", show_alert=True)
        return
    product, stock_count = product_row
    await callback.message.edit_text(
        f"Product #{product.id}\n\n"
        f"Name: {product.name}\n"
        f"Price: {money(product.price)}\n"
        f"Stock: {stock_count}\n"
        f"Status: {'active' if product.is_active else 'disabled'}\n\n"
        f"{product.description}",
        reply_markup=product_admin_actions(product.id, product.is_active),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_product")
async def add_product_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    await state.set_state(ProductForm.details)
    await callback.message.edit_text(
        "Send product details in this format:\n\n"
        "Name | Price | Description\n\n"
        "Example:\nGmail Fresh | 2.50 | Fresh Gmail accounts",
        reply_markup=back_menu(),
    )
    await callback.answer()


@router.message(ProductForm.details)
async def add_product_finish(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = [part.strip() for part in message.text.split("|", 2)]
    if len(parts) != 3:
        await message.answer("Invalid format. Use: Name | Price | Description")
        return
    try:
        product = await create_product(session, parts[0], float(parts[1]), parts[2])
    except ValueError:
        await message.answer("Price must be a number.")
        return
    await state.clear()
    await message.answer(f"Created product #{product.id}: {product.name}", reply_markup=product_admin_actions(product.id, True))


@router.callback_query(F.data == "admin_add_stock")
async def add_stock_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    products = await list_all_products(session)
    if not products:
        await callback.message.edit_text("Create a product before adding stock.", reply_markup=admin_menu())
    else:
        await state.set_state(StockForm.product_id)
        await callback.message.edit_text(
            "Send the product ID to stock.\n\n"
            + "\n".join(f"#{product.id} {product.name}" for product, _ in products),
            reply_markup=back_menu(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_stock_for:"))
async def add_stock_for_product(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    product_id = int(callback.data.split(":", 1)[1])
    await state.update_data(product_id=product_id)
    await state.set_state(StockForm.payload)
    await callback.message.edit_text(
        "Send bulk stock lines, one item per line.\n\n"
        "email1@example.com|password1\nemail2@example.com|password2",
        reply_markup=back_menu(),
    )
    await callback.answer()


@router.message(StockForm.product_id)
async def stock_product_id(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    try:
        product_id = int(message.text)
    except (TypeError, ValueError):
        await message.answer("Send a numeric product ID.")
        return
    await state.update_data(product_id=product_id)
    await state.set_state(StockForm.payload)
    await message.answer(
        "Send bulk stock lines, one item per line.\n\n"
        "email1@example.com|password1\nemail2@example.com|password2"
    )


@router.message(StockForm.payload)
async def stock_payload(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    count = await add_stock(session, int(data["product_id"]), message.text.splitlines())
    await state.clear()
    await message.answer(f"Added {count} stock item(s).", reply_markup=admin_menu())


@router.callback_query(F.data.startswith("admin_toggle_product:"))
async def admin_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    product_id = int(callback.data.split(":", 1)[1])
    product = await toggle_product(session, product_id)
    if not product:
        await callback.answer("Product not found.", show_alert=True)
        return
    await callback.message.edit_text(
        f"{product.name} is now {'active' if product.is_active else 'disabled'}.",
        reply_markup=product_admin_actions(product.id, product.is_active),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_delete_product:"))
async def admin_delete_product(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    product_id = int(callback.data.split(":", 1)[1])
    await callback.message.edit_text(
        "Delete this product?\n\n"
        "If this product already has orders, it will be disabled and only unsold stock will be removed.",
        reply_markup=delete_product_confirm(product_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_delete_product_confirm:"))
async def admin_delete_product_finish(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    product_id = int(callback.data.split(":", 1)[1])
    ok, text = await delete_product(session, product_id)
    if not ok:
        await callback.answer(text, show_alert=True)
        return
    await callback.message.edit_text(text, reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin_deposits")
async def deposits(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    rows = await pending_deposits(session)
    if not rows:
        await callback.message.edit_text("No pending deposits.", reply_markup=admin_menu())
    else:
        first = rows[0]
        await callback.message.edit_text(
            f"Pending deposit #{first.id}\n\n"
            f"User ID: {first.user_id}\n"
            f"Amount: {money(first.amount)}\n"
            f"Method: {first.method}\n"
            f"TXID: {first.transaction_id}\n\n"
            f"Queue size: {len(rows)}",
            reply_markup=deposit_review(first.id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("deposit_approve:") | F.data.startswith("deposit_reject:"))
async def review_deposit_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    action, raw_id = callback.data.split(":", 1)
    deposit = await review_deposit(session, int(raw_id), approve=action == "deposit_approve")
    if not deposit:
        await callback.answer("Deposit not found or already reviewed.", show_alert=True)
        return
    await callback.message.edit_text(
        f"Deposit #{deposit.id} {deposit.status.value}.",
        reply_markup=admin_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_coupon")
async def add_coupon_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    await state.set_state(CouponAdminForm.details)
    await callback.message.edit_text(
        "Send coupon details:\n\n"
        "CODE | Amount | Max Uses\n\n"
        "Example:\nWELCOME10 | 1.00 | 100",
        reply_markup=back_menu(),
    )
    await callback.answer()


@router.message(CouponAdminForm.details)
async def add_coupon_finish(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = [part.strip() for part in message.text.split("|")]
    if len(parts) != 3:
        await message.answer("Invalid format. Use: CODE | Amount | Max Uses")
        return
    try:
        coupon = await create_coupon(session, parts[0], float(parts[1]), int(parts[2]))
    except ValueError:
        await message.answer("Amount and max uses must be numeric.")
        return
    await state.clear()
    await message.answer(
        f"Created coupon {coupon.code} worth {money(coupon.amount)}.",
        reply_markup=admin_menu(),
    )
