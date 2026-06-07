from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_reply_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="Shop Now"), KeyboardButton(text="Deposit")],
        [KeyboardButton(text="Profile"), KeyboardButton(text="Refer")],
        [KeyboardButton(text="Coupon"), KeyboardButton(text="Orders")],
        [KeyboardButton(text="Support")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder="Choose a menu")


def products_reply_menu(products: list[tuple[object, int]], is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = []
    product_buttons = [KeyboardButton(text=product.name) for product, _ in products]
    for index in range(0, len(product_buttons), 2):
        rows.append(product_buttons[index : index + 2])
    rows.append([KeyboardButton(text="Main Menu")])
    if is_admin:
        rows.append([KeyboardButton(text="Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder="Choose a product")


def product_buy_reply_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="Single Buy"), KeyboardButton(text="Bulk Buy")],
        [KeyboardButton(text="Shop Now"), KeyboardButton(text="Main Menu")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder="Choose buy option")


def deposit_methods_reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Binance"), KeyboardButton(text="USDT TRC20")],
            [KeyboardButton(text="USDT BEP20"), KeyboardButton(text="bKash")],
            [KeyboardButton(text="Nagad"), KeyboardButton(text="Rocket")],
            [KeyboardButton(text="Main Menu")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Choose payment method",
    )
