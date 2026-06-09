from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_reply_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🛍 Shop"), KeyboardButton(text="💼 Sell"), KeyboardButton(text="💳 Top Up")],
        [KeyboardButton(text="🤖 AI"), KeyboardButton(text="👤 Profile"), KeyboardButton(text="📦 Orders")],
        [KeyboardButton(text="🏷 Coupon"), KeyboardButton(text="🎁 Refer"), KeyboardButton(text="🧾 Status")],
        [KeyboardButton(text="☎️ Support")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Select an option",
    )


def products_reply_menu(products: list[tuple[object, int]], is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = []
    product_buttons = [KeyboardButton(text=f"🛒 {product.name}") for product, _ in products]
    for index in range(0, len(product_buttons), 2):
        rows.append(product_buttons[index : index + 2])
    rows.append([KeyboardButton(text="🏠 Main Menu")])
    if is_admin:
        rows.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Select product",
    )


def product_buy_reply_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🛒 Single"), KeyboardButton(text="📦 Bulk"), KeyboardButton(text="🏠 Menu")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Select purchase type",
    )


def deposit_methods_reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🟡 Binance"), KeyboardButton(text="TRC20"), KeyboardButton(text="BEP20")],
            [KeyboardButton(text="bKash"), KeyboardButton(text="Nagad"), KeyboardButton(text="Rocket")],
            [KeyboardButton(text="🏠 Main Menu")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Select payment method",
    )
