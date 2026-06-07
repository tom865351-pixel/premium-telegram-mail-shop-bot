import csv
import re
from io import BytesIO, StringIO

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.keyboards.admin import (
    admin_reply_menu,
    admin_products_reply_menu,
    delete_product_confirm_reply_menu,
    deposit_review_reply_menu,
    member_actions_reply_menu,
    product_admin_actions_reply_menu,
)
from bot.services.coupons import create_coupon
from bot.services.deposits import pending_deposits, review_deposit
from bot.services.products import add_stock, create_product, delete_product, list_all_products, toggle_product, update_product
from bot.services.stats import admin_stats
from bot.services.users import adjust_user_balance, find_user, set_user_banned, set_user_restricted
from bot.utils.formatting import money

router = Router()

SUPPORTED_STOCK_EXTENSIONS = (".xlsx", ".csv", ".txt")


class ProductForm(StatesGroup):
    details = State()


class ProductEditForm(StatesGroup):
    details = State()


class StockForm(StatesGroup):
    product_id = State()
    payload = State()


class CouponAdminForm(StatesGroup):
    details = State()


class MemberLookupForm(StatesGroup):
    query = State()


class MemberBalanceForm(StatesGroup):
    amount = State()


def is_admin(user_id: int) -> bool:
    return user_id in get_settings().admin_ids


def _button_text(text: str) -> str:
    return re.sub(r"^[^A-Za-z0-9#]+", "", text.strip()).strip()


def _starts_with_any(text: str, prefixes: tuple[str, ...]) -> bool:
    normalized = _button_text(text)
    upper_normalized = normalized.upper()
    return any(normalized.startswith(prefix) or upper_normalized.startswith(prefix.upper()) for prefix in prefixes)


def _is_product_selection(text: str) -> bool:
    return _starts_with_any(text, ("Product #",))


def _is_add_stock_action(text: str) -> bool:
    return _starts_with_any(text, ("Add Stock #",))


def _is_edit_product_action(text: str) -> bool:
    return _starts_with_any(text, ("Edit Product #",))


def _is_product_action(text: str) -> bool:
    return _starts_with_any(
        text,
        (
            "Enable Product #",
            "Disable Product #",
            "Delete Product #",
            "Cancel Product #",
        ),
    )


def _is_delete_confirm(text: str) -> bool:
    return _starts_with_any(text, ("Confirm Delete Product #",))


def _is_deposit_review(text: str) -> bool:
    return _starts_with_any(text, ("Approve Deposit #", "Reject Deposit #"))


def _is_deposit_approve(text: str) -> bool:
    return _starts_with_any(text, ("Approve Deposit #",))


def _is_member_action(text: str) -> bool:
    return _starts_with_any(
        text,
        (
            "Add Balance #",
            "Remove Balance #",
            "Check Orders #",
            "Check Balance #",
            "Ban Member #",
            "Unban Member #",
            "Restrict Member #",
            "Unrestrict Member #",
        ),
    )


def _member_status(user: object) -> str:
    flags = []
    if getattr(user, "is_banned", False):
        flags.append("Banned")
    if getattr(user, "is_restricted", False):
        flags.append("Restricted")
    return ", ".join(flags) if flags else "Normal"


def _member_text(user: object) -> str:
    username = f"@{user.username}" if user.username else "not_available"
    return (
        "Member Details\n\n"
        f"Database ID: #{user.id}\n"
        f"Name: {user.first_name or 'Unknown'}\n"
        f"Username: {username}\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Balance: {money(user.balance)}\n"
        f"Status: {_member_status(user)}"
    )


def _id_from_hash_button(text: str, prefix: str) -> int | None:
    normalized = _button_text(text)
    if not normalized.startswith(prefix):
        return None
    match = re.search(r"#\s*(\d+)", normalized)
    if not match:
        return None
    return int(match.group(1))


def _method_label(method: str) -> str:
    labels = {
        "binance": "Binance",
        "usdt_trc20": "USDT TRC20",
        "usdt_bep20": "USDT BEP20",
        "bkash": "bKash",
        "nagad": "Nagad",
        "rocket": "Rocket",
    }
    return labels.get(method, method.upper())


async def _deposit_details_text(session: AsyncSession, deposit: object, queue_size: int | None = None) -> str:
    from bot.database.models import User

    user = await session.get(User, deposit.user_id)
    queue_line = f"\nQueue Size: {queue_size}" if queue_size is not None else ""
    username = f"@{user.username}" if user and user.username else "not_available"
    name = user.first_name if user and user.first_name else "Unknown"
    telegram_id = user.telegram_id if user else "Unknown"
    return (
        "Pending Deposit Request\n\n"
        f"Request ID: #{deposit.id}\n"
        f"Amount: {money(deposit.amount)}\n"
        f"Method: {_method_label(deposit.method)}\n"
        f"Transaction ID: <code>{deposit.transaction_id}</code>\n"
        f"Status: {deposit.status.value}\n"
        f"Created: {deposit.created_at:%Y-%m-%d %H:%M}"
        f"{queue_line}\n\n"
        "Customer Information\n"
        f"Name: {name}\n"
        f"Username: {username}\n"
        f"Telegram ID: <code>{telegram_id}</code>\n\n"
        "Verify the payment manually, then approve or reject."
    )


async def _send_next_deposit_after_review(message: Message, session: AsyncSession, deposit: object) -> None:
    await message.answer(
        f"Deposit Reviewed\n\nRequest ID: #{deposit.id}\nStatus: {deposit.status.value}\nAmount: {money(deposit.amount)}"
    )
    rows = await pending_deposits(session)
    if not rows:
        await message.answer("Deposits\n\nNo pending deposit requests.", reply_markup=admin_reply_menu())
        return
    first = rows[0]
    await message.answer(
        await _deposit_details_text(session, first, len(rows)),
        reply_markup=deposit_review_reply_menu(first.id),
    )


def _looks_like_header(values: list[str]) -> bool:
    header_words = {"email", "mail", "username", "user", "password", "pass", "account", "accounts"}
    lowered = {value.strip().lower() for value in values if value.strip()}
    return bool(lowered & header_words)


def _stock_line_from_cells(cells: list[object]) -> str | None:
    values = [str(cell).strip() for cell in cells if cell is not None and str(cell).strip()]
    if not values or _looks_like_header(values):
        return None
    if len(values) >= 2:
        return f"{values[0]}|{values[1]}"
    return values[0]


def parse_stock_file(file_name: str, data: bytes) -> list[str]:
    lowered = file_name.lower()
    if lowered.endswith(".xlsx"):
        workbook = load_workbook(BytesIO(data), read_only=True, data_only=True)
        worksheet = workbook.active
        lines = []
        for row in worksheet.iter_rows(values_only=True):
            line = _stock_line_from_cells(list(row))
            if line:
                lines.append(line)
        workbook.close()
        return lines

    if lowered.endswith(".csv"):
        text = data.decode("utf-8-sig", errors="ignore")
        rows = csv.reader(StringIO(text))
        return [line for row in rows if (line := _stock_line_from_cells(row))]

    if lowered.endswith(".txt"):
        text = data.decode("utf-8-sig", errors="ignore")
        return [line.strip() for line in text.splitlines() if line.strip()]

    raise ValueError("Unsupported file type.")


@router.message(Command("admin"))
async def admin_command(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("You are not authorized.")
        return
    await message.answer(
        "Admin Panel\n\nManage products, stock, deposits, coupons, and store statistics.",
        reply_markup=admin_reply_menu(),
    )


@router.callback_query(F.data == "admin")
async def admin_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    await callback.message.edit_text("Admin Panel")
    await callback.message.answer(
        "Admin Panel\n\nManage products, stock, deposits, coupons, and store statistics.",
        reply_markup=admin_reply_menu(),
    )
    await callback.answer()


@router.message(StateFilter("*"), F.text.in_({"Admin Panel", "ADMIN PANEL", "⚙️ Admin Panel"}))
async def admin_panel_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("You are not authorized.")
        return
    await message.answer(
        "Admin Panel\n\nManage products, stock, deposits, coupons, and store statistics.",
        reply_markup=admin_reply_menu(),
    )


@router.callback_query(F.data == "admin_stats")
async def stats(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    data = await admin_stats(session)
    await callback.message.edit_text(
        "Store Statistics\n\n"
        f"Users: {data['users']}\n"
        f"Products: {data['products']}\n"
        f"Unsold stock: {data['stock']}\n"
        f"Orders: {data['orders']}\n"
        f"Revenue: {money(data['revenue'])}\n"
        f"Pending deposits: {data['pending_deposits']}",
    )
    await callback.message.answer("Admin Panel", reply_markup=admin_reply_menu())
    await callback.answer()


@router.message(StateFilter("*"), F.text.in_({"Stats", "STATS", "📊 Stats"}))
async def stats_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("You are not authorized.")
        return
    data = await admin_stats(session)
    await message.answer(
        "Store Statistics\n\n"
        f"Users: {data['users']}\n"
        f"Products: {data['products']}\n"
        f"Unsold stock: {data['stock']}\n"
        f"Orders: {data['orders']}\n"
        f"Revenue: {money(data['revenue'])}\n"
        f"Pending deposits: {data['pending_deposits']}",
        reply_markup=admin_reply_menu(),
    )


@router.message(StateFilter("*"), F.text.in_({"Members", "MEMBERS", "👥 Members"}))
async def members_start_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("You are not authorized.")
        return
    await state.set_state(MemberLookupForm.query)
    await message.answer(
        "Member Management\n\n"
        "Send member Telegram ID or username.\n\n"
        "Example:\n"
        "7562995992\n"
        "@username"
    )


@router.message(MemberLookupForm.query)
async def member_lookup_finish(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    user = await find_user(session, message.text)
    await state.clear()
    if not user:
        await message.answer("Member not found.", reply_markup=admin_reply_menu())
        return
    await message.answer(
        _member_text(user),
        reply_markup=member_actions_reply_menu(user.id, user.is_banned, user.is_restricted),
    )


@router.message(StateFilter("*"), F.text.func(_is_member_action))
async def member_action_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("You are not authorized.")
        return

    action_text = _button_text(message.text)
    user_id = None
    for prefix in (
        "Add Balance #",
        "Remove Balance #",
        "Check Orders #",
        "Check Balance #",
        "Ban Member #",
        "Unban Member #",
        "Restrict Member #",
        "Unrestrict Member #",
    ):
        user_id = _id_from_hash_button(message.text, prefix)
        if user_id:
            break
    if not user_id:
        await message.answer("Invalid member action.", reply_markup=admin_reply_menu())
        return

    from bot.database.models import User

    user = await session.get(User, user_id)
    if not user:
        await message.answer("Member not found.", reply_markup=admin_reply_menu())
        return
    if user.telegram_id in get_settings().admin_ids and (
        action_text.startswith("Ban Member #")
        or action_text.startswith("Restrict Member #")
    ):
        await message.answer("Admin accounts cannot be banned or restricted.", reply_markup=admin_reply_menu())
        return

    if action_text.startswith("Add Balance #") or action_text.startswith("Remove Balance #"):
        action = "add" if action_text.startswith("Add Balance #") else "remove"
        await state.update_data(member_id=user.id, balance_action=action)
        await state.set_state(MemberBalanceForm.amount)
        await message.answer(
            f"{'Add' if action == 'add' else 'Remove'} Balance\n\n"
            f"Member: {user.first_name or user.telegram_id}\n"
            f"Current Balance: {money(user.balance)}\n\n"
            "Send amount."
        )
        return

    if action_text.startswith("Check Balance #"):
        await message.answer(
            _member_text(user),
            reply_markup=member_actions_reply_menu(user.id, user.is_banned, user.is_restricted),
        )
        return

    if action_text.startswith("Check Orders #"):
        from bot.services.orders import recent_orders

        orders = await recent_orders(session, user.id, limit=10)
        if not orders:
            text = "Member Orders\n\nNo orders found."
        else:
            text = "Member Orders\n\n" + "\n".join(
                f"#{order.id} - {money(order.amount)} - {order.created_at:%Y-%m-%d %H:%M}"
                for order in orders
            )
        await message.answer(text, reply_markup=member_actions_reply_menu(user.id, user.is_banned, user.is_restricted))
        return

    if action_text.startswith("Ban Member #") or action_text.startswith("Unban Member #"):
        banned = action_text.startswith("Ban Member #")
        user = await set_user_banned(session, user.id, banned)
        await message.answer(
            f"Member {'Banned' if banned else 'Unbanned'}\n\n{_member_text(user)}",
            reply_markup=member_actions_reply_menu(user.id, user.is_banned, user.is_restricted),
        )
        return

    if action_text.startswith("Restrict Member #") or action_text.startswith("Unrestrict Member #"):
        restricted = action_text.startswith("Restrict Member #")
        user = await set_user_restricted(session, user.id, restricted)
        await message.answer(
            f"Member {'Restricted' if restricted else 'Unrestricted'}\n\n{_member_text(user)}",
            reply_markup=member_actions_reply_menu(user.id, user.is_banned, user.is_restricted),
        )


@router.message(MemberBalanceForm.amount)
async def member_balance_finish(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    try:
        amount = float(message.text)
    except (TypeError, ValueError):
        await message.answer("Please send a valid numeric amount.")
        return
    if amount <= 0:
        await message.answer("Amount must be greater than 0.")
        return

    data = await state.get_data()
    signed_amount = amount if data["balance_action"] == "add" else -amount
    user = await adjust_user_balance(session, int(data["member_id"]), signed_amount)
    await state.clear()
    if not user:
        await message.answer("Member not found.", reply_markup=admin_reply_menu())
        return
    await message.answer(
        f"Balance Updated\n\n"
        f"Member: {user.first_name or user.telegram_id}\n"
        f"New Balance: {money(user.balance)}",
        reply_markup=member_actions_reply_menu(user.id, user.is_banned, user.is_restricted),
    )


@router.callback_query(F.data == "admin_products")
async def admin_products(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    rows = await list_all_products(session)
    if not rows:
        await callback.message.edit_text("No products created.")
        await callback.message.answer("Admin Panel", reply_markup=admin_reply_menu())
    else:
        text = "Product List\n\n" + "\n".join(
            f"#{product.id} {product.name} - {money(product.price)} - stock {stock} - {'active' if product.is_active else 'disabled'}"
            for product, stock in rows
        )
        await callback.message.edit_text(text)
        await callback.message.answer("Select a product from the keyboard.", reply_markup=admin_products_reply_menu(rows))
    await callback.answer()


@router.message(StateFilter("*"), F.text.in_({"Products", "PRODUCTS", "📦 Products"}))
async def admin_products_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("You are not authorized.")
        return
    rows = await list_all_products(session)
    if not rows:
        await message.answer("No products created.", reply_markup=admin_reply_menu())
    else:
        text = "Product List\n\n" + "\n".join(
            f"#{product.id} {product.name} - {money(product.price)} - stock {stock} - {'active' if product.is_active else 'disabled'}"
            for product, stock in rows
        )
        await message.answer(text, reply_markup=admin_products_reply_menu(rows))


@router.message(StateFilter("*"), F.text.func(_is_product_selection))
async def admin_product_detail_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("You are not authorized.")
        return
    product_id = _id_from_hash_button(message.text, "Product #")
    if not product_id:
        await message.answer("Invalid product selection.")
        return
    rows = await list_all_products(session)
    product_row = next((row for row in rows if row[0].id == product_id), None)
    if not product_row:
        await message.answer("Product not found.", reply_markup=admin_reply_menu())
        return
    product, stock_count = product_row
    await message.answer(
        f"Product Details\n\n"
        f"Product ID: #{product.id}\n"
        f"Name: {product.name}\n"
        f"Price: {money(product.price)}\n"
        f"Available Stock: {stock_count}\n"
        f"Status: {'Active' if product.is_active else 'Disabled'}\n\n"
        f"Description: {product.description or 'No description provided.'}",
        reply_markup=product_admin_actions_reply_menu(product.id, product.is_active),
    )


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
    )
    await callback.message.answer(
        "Choose product action.",
        reply_markup=product_admin_actions_reply_menu(product.id, product.is_active),
    )
    await callback.answer()


@router.message(StateFilter("*"), F.text.in_({"Add Product", "ADD PRODUCT", "➕ Add Product"}))
async def add_product_start_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("You are not authorized.")
        return
    await state.set_state(ProductForm.details)
    await message.answer(
        "Add Product\n\nSend product details in this format:\n\n"
        "Name | Price | Description\n\n"
        "Example:\nGmail Fresh | 120 | Fresh Gmail accounts"
    )


@router.callback_query(F.data == "admin_add_product")
async def add_product_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    await state.set_state(ProductForm.details)
    await callback.message.edit_text(
        "Add Product\n\nSend product details in this format:\n\n"
        "Name | Price | Description\n\n"
        "Example:\nGmail Fresh | 2.50 | Fresh Gmail accounts"
    )
    await callback.answer()


@router.message(StateFilter("*"), F.text.in_({"Add Stock", "ADD STOCK", "📥 Add Stock"}))
async def add_stock_start_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("You are not authorized.")
        return
    products = await list_all_products(session)
    if not products:
        await message.answer("Create a product before adding stock.", reply_markup=admin_reply_menu())
    else:
        await state.set_state(StockForm.product_id)
        await message.answer(
            "Send the product ID to stock.\n\n"
            + "\n".join(f"#{product.id} {product.name}" for product, _ in products)
        )


@router.message(ProductForm.details)
async def add_product_finish(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = [part.strip() for part in message.text.split("|", 2)]
    if len(parts) != 3:
        await message.answer("Invalid format.\n\nUse: Name | Price | Description")
        return
    try:
        product = await create_product(session, parts[0], float(parts[1]), parts[2])
    except ValueError:
        await message.answer("Product price must be a valid number.")
        return
    await state.clear()
    await message.answer(
        f"Product Created\n\nProduct ID: #{product.id}\nName: {product.name}\nPrice: {money(product.price)}",
        reply_markup=product_admin_actions_reply_menu(product.id, True),
    )


@router.message(StateFilter("*"), F.text.func(_is_edit_product_action))
async def edit_product_start_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("You are not authorized.")
        return
    product_id = _id_from_hash_button(message.text, "Edit Product #")
    if not product_id:
        await message.answer("Invalid product action.")
        return
    rows = await list_all_products(session)
    product_row = next((row for row in rows if row[0].id == product_id), None)
    if not product_row:
        await message.answer("Product not found.", reply_markup=admin_reply_menu())
        return
    product, _ = product_row
    await state.update_data(product_id=product.id)
    await state.set_state(ProductEditForm.details)
    await message.answer(
        "Edit Product\n\n"
        "Send updated product details in this format:\n\n"
        "Name | Price | Description\n\n"
        "Current:\n"
        f"{product.name} | {float(product.price):.2f} | {product.description or ''}"
    )


@router.message(ProductEditForm.details)
async def edit_product_finish(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = [part.strip() for part in message.text.split("|", 2)]
    if len(parts) != 3:
        await message.answer("Invalid format.\n\nUse: Name | Price | Description")
        return
    try:
        price = float(parts[1])
    except ValueError:
        await message.answer("Product price must be a valid number.")
        return

    data = await state.get_data()
    try:
        product = await update_product(session, int(data["product_id"]), parts[0], price, parts[2])
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await state.clear()
    if not product:
        await message.answer("Product not found.", reply_markup=admin_reply_menu())
        return
    await message.answer(
        f"Product Updated\n\nProduct ID: #{product.id}\nName: {product.name}\nPrice: {money(product.price)}",
        reply_markup=product_admin_actions_reply_menu(product.id, product.is_active),
    )


@router.callback_query(F.data == "admin_add_stock")
async def add_stock_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    products = await list_all_products(session)
    if not products:
        await callback.message.edit_text("Create a product before adding stock.")
        await callback.message.answer("Admin Panel", reply_markup=admin_reply_menu())
    else:
        await state.set_state(StockForm.product_id)
        await callback.message.edit_text(
            "Send the product ID to stock.\n\n"
            + "\n".join(f"#{product.id} {product.name}" for product, _ in products)
        )
    await callback.answer()


@router.message(StateFilter("*"), F.text.func(_is_add_stock_action))
async def add_stock_for_product_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("You are not authorized.")
        return
    product_id = _id_from_hash_button(message.text, "Add Stock #")
    if not product_id:
        await message.answer("Invalid product action.")
        return
    await state.update_data(product_id=product_id)
    await state.set_state(StockForm.payload)
    await message.answer(
        "Send bulk stock lines, one item per line, or upload .xlsx/.csv/.txt.\n\n"
        "email1@example.com|password1\nemail2@example.com|password2"
    )


@router.message(StateFilter("*"), F.text.in_({"Deposits", "DEPOSITS", "💳 Deposits"}))
async def deposits_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("You are not authorized.")
        return
    rows = await pending_deposits(session)
    if not rows:
        await message.answer("Deposits\n\nNo pending deposit requests.", reply_markup=admin_reply_menu())
    else:
        first = rows[0]
        await message.answer(
            await _deposit_details_text(session, first, len(rows)),
            reply_markup=deposit_review_reply_menu(first.id),
        )


@router.callback_query(F.data.startswith("admin_stock_for:"))
async def add_stock_for_product(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    product_id = int(callback.data.split(":", 1)[1])
    await state.update_data(product_id=product_id)
    await state.set_state(StockForm.payload)
    await callback.message.edit_text(
        "Send bulk stock lines, one item per line, or upload .xlsx/.csv/.txt.\n\n"
        "email1@example.com|password1\nemail2@example.com|password2"
    )
    await callback.answer()


@router.message(StateFilter("*"), F.text.in_({"Coupons", "COUPONS", "🏷 Coupons"}))
async def add_coupon_start_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("You are not authorized.")
        return
    await state.set_state(CouponAdminForm.details)
    await message.answer(
        "Send coupon details:\n\n"
        "CODE | Amount | Max Uses\n\n"
        "Example:\nWELCOME10 | 100 | 100"
    )


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
        "Send bulk stock lines, one item per line, or upload .xlsx/.csv/.txt.\n\n"
        "email1@example.com|password1\nemail2@example.com|password2"
    )


@router.message(StockForm.payload, F.document)
async def stock_payload_file(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return

    document = message.document
    file_name = document.file_name or ""
    if not file_name.lower().endswith(SUPPORTED_STOCK_EXTENSIONS):
        await message.answer("Unsupported file type. Please upload only .xlsx, .csv, or .txt stock files.")
        return

    buffer = BytesIO()
    await message.bot.download(document, destination=buffer)
    try:
        lines = parse_stock_file(file_name, buffer.getvalue())
    except ValueError as exc:
        await message.answer(str(exc))
        return

    if not lines:
        await message.answer("No valid stock lines found in this file.")
        return

    data = await state.get_data()
    count = await add_stock(session, int(data["product_id"]), lines)
    await state.clear()
    await message.answer(
        f"Stock Uploaded\n\nFile: {file_name}\nAdded Items: {count}",
        reply_markup=admin_reply_menu(),
    )


@router.message(StockForm.payload)
async def stock_payload(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    if not message.text:
        await message.answer("Send stock text or upload a .xlsx/.csv/.txt file.")
        return
    data = await state.get_data()
    count = await add_stock(session, int(data["product_id"]), message.text.splitlines())
    await state.clear()
    await message.answer(f"Stock Added\n\nAdded Items: {count}", reply_markup=admin_reply_menu())


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
    )
    await callback.message.answer(
        "Choose product action.",
        reply_markup=product_admin_actions_reply_menu(product.id, product.is_active),
    )
    await callback.answer()


@router.message(
    StateFilter("*"),
    F.text.func(_is_product_action),
)
async def toggle_or_delete_product_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("You are not authorized.")
        return

    if _starts_with_any(message.text, ("Enable Product #", "Disable Product #")):
        product_id = _id_from_hash_button(message.text, "Enable Product #") or _id_from_hash_button(
            message.text, "Disable Product #"
        )
        if not product_id:
            await message.answer("Invalid product action.")
            return
        product = await toggle_product(session, product_id)
        if not product:
            await message.answer("Product not found.", reply_markup=admin_reply_menu())
            return
        await message.answer(
            f"{product.name} is now {'active' if product.is_active else 'disabled'}.",
            reply_markup=product_admin_actions_reply_menu(product.id, product.is_active),
        )
        return

    if _starts_with_any(message.text, ("Delete Product #",)):
        product_id = _id_from_hash_button(message.text, "Delete Product #")
        if not product_id:
            await message.answer("Invalid product action.")
            return
        await message.answer(
            "Delete this product?\n\n"
            "If this product already has orders, it will be archived from the product list and old order history will stay safe.",
            reply_markup=delete_product_confirm_reply_menu(product_id),
        )
        return

    if _starts_with_any(message.text, ("Cancel Product #",)):
        await message.answer("Cancelled.", reply_markup=admin_reply_menu())


@router.callback_query(F.data.startswith("admin_delete_product:"))
async def admin_delete_product(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    product_id = int(callback.data.split(":", 1)[1])
    await callback.message.edit_text(
        "Delete this product?\n\n"
        "If this product already has orders, it will be archived from the product list and old order history will stay safe.",
    )
    await callback.message.answer("Confirm delete.", reply_markup=delete_product_confirm_reply_menu(product_id))
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
    await callback.message.edit_text(text)
    await callback.message.answer("Admin Panel", reply_markup=admin_reply_menu())
    await callback.answer()


@router.message(
    StateFilter("*"),
    F.text.func(_is_delete_confirm),
)
async def admin_delete_product_finish_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("You are not authorized.")
        return
    product_id = _id_from_hash_button(message.text, "Confirm Delete Product #")
    if not product_id:
        await message.answer("Invalid product action.")
        return
    ok, text = await delete_product(session, product_id)
    await message.answer(text, reply_markup=admin_reply_menu())


@router.callback_query(F.data == "admin_deposits")
async def deposits(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    rows = await pending_deposits(session)
    if not rows:
        await callback.message.edit_text("Deposits\n\nNo pending deposit requests.")
        await callback.message.answer("Admin Panel", reply_markup=admin_reply_menu())
    else:
        first = rows[0]
        await callback.message.edit_text(await _deposit_details_text(session, first, len(rows)))
        await callback.message.answer("Review deposit.", reply_markup=deposit_review_reply_menu(first.id))
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
    from bot.database.models import User

    user = await session.get(User, deposit.user_id)
    if user:
        approve = action == "deposit_approve"
        status_text = "approved" if approve else "rejected"
        try:
            await callback.bot.send_message(
                user.telegram_id,
                "Deposit Update\n\n"
                f"Request ID: #{deposit.id}\n"
                f"Amount: {money(deposit.amount)}\n"
                f"Status: {status_text}\n\n"
                + ("Your balance has been updated." if approve else "Please contact support if this was a mistake."),
            )
        except Exception:
            pass
    await callback.message.edit_text(f"Deposit #{deposit.id} {deposit.status.value}.")
    await _send_next_deposit_after_review(callback.message, session, deposit)
    await callback.answer()


@router.message(
    StateFilter("*"),
    F.text.func(_is_deposit_review),
)
async def review_deposit_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("You are not authorized.")
        return
    approve = _is_deposit_approve(message.text)
    deposit_id = _id_from_hash_button(message.text, "Approve Deposit #" if approve else "Reject Deposit #")
    if not deposit_id:
        await message.answer("Invalid deposit action.")
        return
    deposit = await review_deposit(session, deposit_id, approve=approve)
    if not deposit:
        await message.answer("Deposit not found or already reviewed.", reply_markup=admin_reply_menu())
        return
    from bot.database.models import User

    user = await session.get(User, deposit.user_id)
    if user:
        status_text = "approved" if approve else "rejected"
        try:
            await message.bot.send_message(
                user.telegram_id,
                "Deposit Update\n\n"
                f"Request ID: #{deposit.id}\n"
                f"Amount: {money(deposit.amount)}\n"
                f"Status: {status_text}\n\n"
                + ("Your balance has been updated." if approve else "Please contact support if this was a mistake."),
            )
        except Exception:
            pass
    await _send_next_deposit_after_review(message, session, deposit)


@router.callback_query(F.data == "admin_add_coupon")
async def add_coupon_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    await state.set_state(CouponAdminForm.details)
    await callback.message.edit_text(
        "Send coupon details:\n\n"
        "CODE | Amount | Max Uses\n\n"
        "Example:\nWELCOME10 | 1.00 | 100"
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
        reply_markup=admin_reply_menu(),
    )
