from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_reply_menu(is_admin: bool = False, show_coupon: bool = True, show_sell: bool = True) -> ReplyKeyboardMarkup:
    tools_row = [KeyboardButton(text="🔁 Replace")]
    if show_coupon:
        tools_row.append(KeyboardButton(text="🏷 Coupon"))
    tools_row.append(KeyboardButton(text="🎁 Refer"))
    first_row = [KeyboardButton(text="🛍 Shop"), KeyboardButton(text="💳 Deposit")]
    if show_sell:
        first_row.insert(1, KeyboardButton(text="💼 Sell"))
    rows = [
        first_row,
        [KeyboardButton(text="👤 Profile"), KeyboardButton(text="📜 History")],
        tools_row,
        [KeyboardButton(text="☎️ Support")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="একটি অপশন নির্বাচন করুন",
    )


def history_reply_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="💳 Deposit History"), KeyboardButton(text="📦 Order History")],
        [KeyboardButton(text="🏠 Main Menu")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="হিস্টোরি নির্বাচন করুন",
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
        input_field_placeholder="পণ্য নির্বাচন করুন",
    )


def product_buy_reply_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🛒 Single"), KeyboardButton(text="📦 Bulk"), KeyboardButton(text="🏠 Menu")],
        [KeyboardButton(text="🔁 Replace")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="কেনার ধরন নির্বাচন করুন",
    )


def deposit_methods_reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🟡 Binance")],
            [KeyboardButton(text="📱 bKash"), KeyboardButton(text="📱 Nagad")],
            [KeyboardButton(text="Cancel"), KeyboardButton(text="🏠 Main Menu")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="পেমেন্ট মাধ্যম নির্বাচন করুন",
    )
