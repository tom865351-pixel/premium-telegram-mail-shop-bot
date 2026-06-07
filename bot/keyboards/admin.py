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
        input_field_placeholder="Select admin action",
    )


def admin_products_reply_menu(products: list[tuple[object, int]]) -> ReplyKeyboardMarkup:
    rows = []
    buttons = [KeyboardButton(text=f"Product #{product.id}") for product, _ in products]
    for index in range(0, len(buttons), 2):
        rows.append(buttons[index : index + 2])
    rows.append([KeyboardButton(text="Add Product"), KeyboardButton(text="Add Stock")])
    rows.append([KeyboardButton(text="Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder="Select product")


def deposit_review_reply_menu(deposit_id: int) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"Approve Deposit #{deposit_id}"), KeyboardButton(text=f"Reject Deposit #{deposit_id}")],
            [KeyboardButton(text="Deposits"), KeyboardButton(text="Admin Panel")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Review deposit request",
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
        input_field_placeholder="Select product action",
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
