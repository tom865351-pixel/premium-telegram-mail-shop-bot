from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def members_reply_menu(users: list[object]) -> ReplyKeyboardMarkup:
    rows = []
    buttons = [KeyboardButton(text=f"👤 Member #{user.id}") for user in users]
    for index in range(0, len(buttons), 2):
        rows.append(buttons[index : index + 2])
    rows.append([KeyboardButton(text="🔎 Search Member"), KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Select member",
    )


def admin_reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Products"), KeyboardButton(text="➕ Add Product")],
            [KeyboardButton(text="📥 Add Stock"), KeyboardButton(text="💳 Deposits")],
            [KeyboardButton(text="👥 Members"), KeyboardButton(text="📋 All Members")],
            [KeyboardButton(text="📣 Broadcast"), KeyboardButton(text="📈 Reports")],
            [KeyboardButton(text="🔎 Admin Search"), KeyboardButton(text="📤 Export Data")],
            [KeyboardButton(text="🏷 Coupons"), KeyboardButton(text="📊 Stats")],
            [KeyboardButton(text="🏠 Main Menu")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Select admin action",
    )


def paged_reply_menu(prefix: str, page: int) -> ReplyKeyboardMarkup:
    prev_page = max(page - 1, 1)
    next_page = page + 1
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"⬅️ {prefix} Page {prev_page}"), KeyboardButton(text=f"➡️ {prefix} Page {next_page}")],
            [KeyboardButton(text="⚙️ Admin Panel")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Navigate pages",
    )


def export_reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📤 Export Users"), KeyboardButton(text="📤 Export Orders")],
            [KeyboardButton(text="📤 Export Deposits"), KeyboardButton(text="📤 Export Products")],
            [KeyboardButton(text="⚙️ Admin Panel")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Select export",
    )


def member_actions_reply_menu(user_id: int, is_banned: bool, is_restricted: bool) -> ReplyKeyboardMarkup:
    ban_label = "Unban" if is_banned else "Ban"
    restrict_label = "Unrestrict" if is_restricted else "Restrict"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"💰 Add Balance #{user_id}"), KeyboardButton(text=f"➖ Remove Balance #{user_id}")],
            [KeyboardButton(text=f"🧾 Check Orders #{user_id}"), KeyboardButton(text=f"💳 Check Balance #{user_id}")],
            [KeyboardButton(text=f"📝 Note Member #{user_id}")],
            [KeyboardButton(text=f"🚫 {ban_label} Member #{user_id}"), KeyboardButton(text=f"🔒 {restrict_label} Member #{user_id}")],
            [KeyboardButton(text="📋 All Members"), KeyboardButton(text="👥 Members")],
            [KeyboardButton(text="⚙️ Admin Panel")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Select member action",
    )


def member_orders_reply_menu(user_id: int, orders: list[object]) -> ReplyKeyboardMarkup:
    rows = []
    buttons = [
        KeyboardButton(text=f"↩️ Refund Order #{order.id}")
        for order in orders
        if getattr(getattr(order, "status", None), "value", str(getattr(order, "status", ""))) != "refunded"
    ]
    for index in range(0, len(buttons), 2):
        rows.append(buttons[index : index + 2])
    rows.append([KeyboardButton(text=f"👤 Member #{user_id}"), KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Select order action",
    )


def admin_products_reply_menu(products: list[tuple[object, int]]) -> ReplyKeyboardMarkup:
    rows = []
    buttons = [KeyboardButton(text=f"📦 Product #{product.id}") for product, _ in products]
    for index in range(0, len(buttons), 2):
        rows.append(buttons[index : index + 2])
    rows.append([KeyboardButton(text="➕ Add Product"), KeyboardButton(text="📥 Add Stock")])
    rows.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Select product",
    )


def deposit_review_reply_menu(deposit_id: int) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"✅ Approve Deposit #{deposit_id}"), KeyboardButton(text=f"❌ Reject Deposit #{deposit_id}")],
            [KeyboardButton(text="💳 Deposits"), KeyboardButton(text="⚙️ Admin Panel")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Review deposit request",
    )


def product_admin_actions_reply_menu(product_id: int, is_active: bool) -> ReplyKeyboardMarkup:
    label = "Disable" if is_active else "Enable"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"📥 Add Stock #{product_id}"), KeyboardButton(text=f"🔄 {label} Product #{product_id}")],
            [KeyboardButton(text=f"🌐 Import Stock URL #{product_id}"), KeyboardButton(text=f"📤 Export Stock #{product_id}")],
            [KeyboardButton(text=f"✏️ Edit Product #{product_id}"), KeyboardButton(text=f"🗑 Delete Product #{product_id}")],
            [KeyboardButton(text="📦 Products"), KeyboardButton(text="⚙️ Admin Panel")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Select product action",
    )


def delete_product_confirm_reply_menu(product_id: int) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"✅ Confirm Delete Product #{product_id}")],
            [KeyboardButton(text=f"↩️ Cancel Product #{product_id}"), KeyboardButton(text="⚙️ Admin Panel")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Confirm delete",
    )


def refund_confirm_reply_menu(order_id: int) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"✅ Confirm Refund Order #{order_id}")],
            [KeyboardButton(text="⚙️ Admin Panel")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Confirm refund",
    )
