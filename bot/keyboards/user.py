from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="Dashboard", callback_data="dashboard"),
            InlineKeyboardButton(text="Products", callback_data="products"),
        ],
        [
            InlineKeyboardButton(text="Deposit", callback_data="deposit"),
            InlineKeyboardButton(text="Orders", callback_data="orders"),
        ],
        [
            InlineKeyboardButton(text="Coupon", callback_data="coupon"),
            InlineKeyboardButton(text="Referral", callback_data="referral"),
        ],
        [InlineKeyboardButton(text="Support", callback_data="support")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="Admin Panel", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Back", callback_data="menu")]])


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
