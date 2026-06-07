from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Products", callback_data="admin_products"),
                InlineKeyboardButton(text="Add Product", callback_data="admin_add_product"),
            ],
            [
                InlineKeyboardButton(text="Add Stock", callback_data="admin_add_stock"),
                InlineKeyboardButton(text="Deposits", callback_data="admin_deposits"),
            ],
            [
                InlineKeyboardButton(text="Coupons", callback_data="admin_add_coupon"),
                InlineKeyboardButton(text="Stats", callback_data="admin_stats"),
            ],
            [InlineKeyboardButton(text="Main Menu", callback_data="menu")],
        ]
    )


def deposit_review(deposit_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Approve", callback_data=f"deposit_approve:{deposit_id}"),
                InlineKeyboardButton(text="Reject", callback_data=f"deposit_reject:{deposit_id}"),
            ],
            [InlineKeyboardButton(text="Admin Panel", callback_data="admin")],
        ]
    )


def product_admin_actions(product_id: int, is_active: bool) -> InlineKeyboardMarkup:
    label = "Disable" if is_active else "Enable"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Add Stock", callback_data=f"admin_stock_for:{product_id}"),
                InlineKeyboardButton(text=label, callback_data=f"admin_toggle_product:{product_id}"),
            ],
            [InlineKeyboardButton(text="Admin Panel", callback_data="admin")],
        ]
    )
