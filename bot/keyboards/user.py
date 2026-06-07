from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_reply_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="MAIL SHOP"), KeyboardButton(text="ADD BALANCE")],
        [KeyboardButton(text="MY PROFILE"), KeyboardButton(text="MY ORDERS")],
        [KeyboardButton(text="REFERRAL"), KeyboardButton(text="COUPON")],
        [KeyboardButton(text="SUPPORT")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="ADMIN PANEL")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder="Select an option")


def products_reply_menu(products: list[tuple[object, int]], is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = []
    product_buttons = [KeyboardButton(text=product.name) for product, _ in products]
    for index in range(0, len(product_buttons), 2):
        rows.append(product_buttons[index : index + 2])
    rows.append([KeyboardButton(text="MAIN MENU")])
    if is_admin:
        rows.append([KeyboardButton(text="ADMIN PANEL")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder="Select product")


def product_buy_reply_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="BUY 1 ACCOUNT"), KeyboardButton(text="BULK BUY")],
        [KeyboardButton(text="MAIL SHOP"), KeyboardButton(text="MAIN MENU")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="ADMIN PANEL")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder="Select purchase type")


def deposit_methods_reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Binance"), KeyboardButton(text="USDT TRC20")],
            [KeyboardButton(text="USDT BEP20"), KeyboardButton(text="bKash")],
            [KeyboardButton(text="Nagad"), KeyboardButton(text="Rocket")],
            [KeyboardButton(text="MAIN MENU")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Select payment method",
    )
