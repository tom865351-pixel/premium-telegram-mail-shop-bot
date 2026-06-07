from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def admin_reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="PRODUCTS"), KeyboardButton(text="ADD PRODUCT")],
            [KeyboardButton(text="ADD STOCK"), KeyboardButton(text="DEPOSITS")],
            [KeyboardButton(text="COUPONS"), KeyboardButton(text="STATS")],
            [KeyboardButton(text="MAIN MENU")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Select admin action",
    )


def admin_products_reply_menu(products: list[tuple[object, int]]) -> ReplyKeyboardMarkup:
    rows = []
    buttons = [KeyboardButton(text=f"Product #{product.id}") for product, _ in products]
    for index in range(0, len(buttons), 2):
        rows.append(buttons[index : index + 2])
    rows.append([KeyboardButton(text="ADD PRODUCT"), KeyboardButton(text="ADD STOCK")])
    rows.append([KeyboardButton(text="ADMIN PANEL")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder="Select product")


def deposit_review_reply_menu(deposit_id: int) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"APPROVE DEPOSIT #{deposit_id}"), KeyboardButton(text=f"REJECT DEPOSIT #{deposit_id}")],
            [KeyboardButton(text="DEPOSITS"), KeyboardButton(text="ADMIN PANEL")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Review deposit request",
    )


def product_admin_actions_reply_menu(product_id: int, is_active: bool) -> ReplyKeyboardMarkup:
    label = "Disable" if is_active else "Enable"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"ADD STOCK #{product_id}"), KeyboardButton(text=f"{label.upper()} PRODUCT #{product_id}")],
            [KeyboardButton(text=f"DELETE PRODUCT #{product_id}")],
            [KeyboardButton(text="PRODUCTS"), KeyboardButton(text="ADMIN PANEL")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Select product action",
    )


def delete_product_confirm_reply_menu(product_id: int) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"CONFIRM DELETE PRODUCT #{product_id}")],
            [KeyboardButton(text=f"CANCEL PRODUCT #{product_id}"), KeyboardButton(text="ADMIN PANEL")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Confirm delete",
    )
