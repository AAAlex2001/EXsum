from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


PAGE_SIZE_DAY = 7

def menu_start() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Аналитика дни", callback_data="analytics_days"), InlineKeyboardButton(text="📊 Аналитика месяца", callback_data="analytics_months")],
        [InlineKeyboardButton(text="💰 ДДС", callback_data="dds")], #InlineKeyboardButton(text="⚙️ FIFO", callback_data="fifo")],
    ])
    return keyboard

def dds_keyboard(dates: list[str], page: int):
    start = page * PAGE_SIZE_DAY
    end = start + PAGE_SIZE_DAY
    chunk = dates[start:end]

    keyboard = []

    # кнопки дней
    for d in chunk:
        keyboard.append([
            InlineKeyboardButton(
                text=d,
                callback_data=f"dds:{d}"
            )
        ])

    # пагинация
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"ddss_page:{page-1}"
            )
        )
    if end < len(dates):
        nav.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"ddss_page:{page+1}"
            )
        )

    if nav:
        keyboard.append(nav)

    # назад
    keyboard.append([
        InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def months_keyboard(dates: list[str], page: int):
    start = page * PAGE_SIZE_DAY
    end = start + PAGE_SIZE_DAY
    chunk = dates[start:end]

    keyboard = []

    # кнопки дней
    for d in chunk:
        keyboard.append([
            InlineKeyboardButton(
                text=d,
                callback_data=f"month:{d}"
            )
        ])

    # пагинация
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"months_page:{page-1}"
            )
        )
    if end < len(dates):
        nav.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"months_page:{page+1}"
            )
        )

    if nav:
        keyboard.append(nav)

    # назад
    keyboard.append([
        InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def days_keyboard(dates: list[str], page: int):
    start = page * PAGE_SIZE_DAY
    end = start + PAGE_SIZE_DAY
    chunk = dates[start:end]

    keyboard = []

    # кнопки дней
    for d in chunk:
        keyboard.append([
            InlineKeyboardButton(
                text=d,
                callback_data=f"day:{d}"
            )
        ])

    # пагинация
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"days_page:{page-1}"
            )
        )
    if end < len(dates):
        nav.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"days_page:{page+1}"
            )
        )

    if nav:
        keyboard.append(nav)

    # назад
    keyboard.append([
        InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)