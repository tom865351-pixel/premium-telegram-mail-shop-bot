from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="Shop Now", callback_data="products"),
            InlineKeyboardButton(text="Deposit", callback_data="deposit"),
        ],
        [
            InlineKeyboardButton(text="Profile", callback_data="dashboard"),
            InlineKeyboardButton(text="Refer", callback_data="referral"),
        ],
        [
            InlineKeyboardButton(text="Coupon", callback_data="coupon"),
            InlineKeyboardButton(text="Orders", callback_data="orders"),
        ],
        [InlineKeyboardButton(text="Support", callback_data="support")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="Admin Panel", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Back", callback_data="menu")]])


def products_menu(products: list[tuple[object, int]]) -> InlineKeyboardMarkup:
    rows = []
    for product, stock_count in products:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{product.name} | Stock {stock_count}",
                    callback_data=f"product:{product.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="Back", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def products_reply_menu(products: list[tuple[object, int]], is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = []
    product_buttons = [KeyboardButton(text=product.name) for product, _ in products]
    for index in range(0, len(product_buttons), 2):
        rows.append(product_buttons[index : index + 2])
    rows.append([KeyboardButton(text="Main Menu")])
    if is_admin:
        rows.append([KeyboardButton(text="Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder="Choose a product")


def product_buy_menu(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Single Buy", callback_data=f"buy_one:{product_id}"),
                InlineKeyboardButton(text="Bulk Buy", callback_data=f"bulk_buy:{product_id}"),
            ],
            [InlineKeyboardButton(text="Back", callback_data="products")],
        ]
    )


def deposit_methods() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Binance", callback_data="deposit_method:binance"),
                InlineKeyboardButton(text="USDT TRC20", callback_data="deposit_method:usdt_trc20"),
            ],
            [
                InlineKeyboardButton(text="USDT BEP20", callback_data="deposit_method:usdt_bep20"),
                InlineKeyboardButton(text="bKash", callback_data="deposit_method:bkash"),
            ],
            [
                InlineKeyboardButton(text="Nagad", callback_data="deposit_method:nagad"),
                InlineKeyboardButton(text="Rocket", callback_data="deposit_method:rocket"),
            ],
            [InlineKeyboardButton(text="Back", callback_data="menu")],
        ]
    )


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
