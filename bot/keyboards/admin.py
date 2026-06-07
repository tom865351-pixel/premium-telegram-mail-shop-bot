from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def admin_reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Products"), KeyboardButton(text="Add Product")],
            [KeyboardButton(text="Add Stock"), KeyboardButton(text="Deposits")],
            [KeyboardButton(text="Coupons"), KeyboardButton(text="Stats")],
            [KeyboardButton(text="Main Menu")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Admin action",
    )


def deposit_review_reply_menu(deposit_id: int) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"Approve Deposit #{deposit_id}"), KeyboardButton(text=f"Reject Deposit #{deposit_id}")],
            [KeyboardButton(text="Deposits"), KeyboardButton(text="Admin Panel")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Review deposit",
    )


def product_admin_actions_reply_menu(product_id: int, is_active: bool) -> ReplyKeyboardMarkup:
    label = "Disable" if is_active else "Enable"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"Add Stock #{product_id}"), KeyboardButton(text=f"{label} Product #{product_id}")],
            [KeyboardButton(text=f"Delete Product #{product_id}")],
            [KeyboardButton(text="Products"), KeyboardButton(text="Admin Panel")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Product action",
    )


def delete_product_confirm_reply_menu(product_id: int) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"Confirm Delete Product #{product_id}")],
            [KeyboardButton(text=f"Cancel Product #{product_id}"), KeyboardButton(text="Admin Panel")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Confirm delete",
    )
