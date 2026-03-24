from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram import F
from aiogram import Bot
from asgiref.sync import sync_to_async
from django.utils import timezone
from .funcs import *
from .menu import *
from tgbot.utils import *



start_router = Router()


async def start_message(message, bot):
    try:
        tg_id = message.from_user.id

        if tg_id in [1033806475, 461670529, 8116559941]:
            await bot.send_message(
                chat_id=message.chat.id,
                text="Привет, Хозяин!\n",
                reply_markup=menu_start(),
                parse_mode="Markdown"
            )
        else:
            await bot.send_message(
                chat_id=message.chat.id,
                text="Доступ запрещен",
            )
    except Exception as e:
        await bot.send_message(
            chat_id=message.chat.id,
            text=str(e),
        )


@start_router.message(Command("start"))
async def start(message: types.Message, bot: Bot):
    await start_message(message, bot)


@start_router.callback_query(lambda c: c.data == "analytics_days")
async def analytics_days(call: types.CallbackQuery):
    days = await sync_to_async(get_revenue_days_list, thread_sensitive=False)()

    await call.message.edit_text(
        "📊 Выберите день:",
        reply_markup=days_keyboard(days, page=0)
    )
    await call.answer()

@start_router.callback_query(lambda c: c.data == "analytics_months")
async def analytics_months(call: types.CallbackQuery):
    days = await sync_to_async(get_revenue_months_list, thread_sensitive=False)()

    await call.message.edit_text(
        "📊 Выберите месяц:",
        reply_markup=months_keyboard(days, page=0)
    )
    await call.answer()

@start_router.callback_query(lambda c: c.data == "dds")
async def analytics_dds(call: types.CallbackQuery):
    days = await sync_to_async(get_revenue_months_list, thread_sensitive=False)()
    days = list(reversed(days))
    await call.message.edit_text(
        "📊 Выберите месяц:",
        reply_markup=dds_keyboard(days, page=0)
    )
    await call.answer()

@start_router.callback_query(lambda c: c.data.startswith("ddss_page:"))
async def analytics_ddss_page(call: types.CallbackQuery):
    await call.answer("Считываю месяца ⏳")
    page = int(call.data.split(":")[1])
    months = await sync_to_async(get_revenue_months_list, thread_sensitive=False)()
    months = list(reversed(months))
    await call.message.edit_text(
        "📊 Выберите месяц:",
        reply_markup=dds_keyboard(months, page=page)
    )

@start_router.callback_query(lambda c: c.data.startswith("months_page:"))
async def analytics_months_page(call: types.CallbackQuery):
    await call.answer("Считываю месяца ⏳")
    page = int(call.data.split(":")[1])
    months = await sync_to_async(get_revenue_months_list, thread_sensitive=False)()

    await call.message.edit_text(
        "📊 Выберите месяц:",
        reply_markup=months_keyboard(months, page=page)
    )

@start_router.callback_query(lambda c: c.data.startswith("days_page:"))
async def analytics_days_page(call: types.CallbackQuery):
    await call.answer("Считываю дни ⏳")
    page = int(call.data.split(":")[1])
    days = await sync_to_async(get_revenue_days_list, thread_sensitive=False)()

    await call.message.edit_text(
        "📊 Выберите день:",
        reply_markup=days_keyboard(days, page=page)
    )
    #await call.answer()



@start_router.callback_query(lambda c: c.data.startswith("day:"))
async def show_day(call: types.CallbackQuery):
    await call.answer("Считаю аналитику ⏳")
    date_str = call.data.split(":", 1)[1]
    await call.message.edit_text("📊 Считаю аналитику, подожди…")
    row = await sync_to_async(get_revenue_day_detail, thread_sensitive=False)(date_str)

    text = (
        f"📅 {row['Дата']}\n\n"
        f"💰 ДОХОД ОБЩИЙ: {row['Доход общий']}\n"
        f"БЕЗ КОНТРАГЕНТА {row['Без контрагента']}\n"
        #f"Моя метрика USD: {row['Моя метрика USD']}\n"
        #f"Комиссия: {row['Комиссия']}\n"
        #f"Моя метрика USDT: {row['Моя метрика USDT']}\n"
        #f"Никита: {row['Никита']}\n"
        f"Доход ИП {row['Доход ИП']}"
    )
    text = (
        f"📅 {row['Дата']}\n"
        f"💰 ДОХОД ОБЩИЙ: {row['Доход общий']}\n"
        f"├ БЕЗ КОНТРАГЕНТА {row['Без контрагента']}\n"
        f"└ ИП {row['Доход ИП']}"
    )


    await call.message.answer(text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="analytics_days")]
        ]),
        parse_mode="Markdown")

@start_router.callback_query(lambda c: c.data.startswith("dds:"))
async def show_dds(call: types.CallbackQuery):
    try:
        await call.answer("Считаю ддс ⏳")
        month_str = call.data.split(":", 1)[1]  # например "09.2024"

        await call.message.edit_text("📊 Считаю ддс за месяц, подожди…")
        row, all_data = await sync_to_async(
            get_dds_detail,
            thread_sensitive=False
        )(month_str)
        """lines = []
        for key, value in row.items():
            lines.append(f"{key} {value}")"""
        lines = []
        lines.append('💸 ДДС-отчёт за {0}'.format(all_data['month_str']))
        lines.append('\n')
        lines.append('📉 Расходы компании: {0}'.format(str(all_data['all_expense'])))
        expenses = all_data['expenses']
        for i, item in enumerate(expenses):
            for key, value in item.items():
                prefix = "└" if i == len(expenses) - 1 else "├"
                lines.append("{0} {1} - {2}".format(prefix, str(key), str(value)))
        lines.append('\n')
        lines.append('📈 Доходы компании: {0}'.format(str(all_data['all_income'])))
        incomes = all_data['incomes']
        for i, item in enumerate(incomes):
            for key, value in item.items():
                prefix = '├'#"└" if i == len(incomes) - 1 else "├"
                #lines.append("├ {0} - {1}".format(str(key), str(value)))
                lines.append("{0} {1} - {2}".format(prefix, str(key), str(value)))
        lines.append("└ Доход общий - {0}".format(str(all_data['total_profit'])))
        lines.append('\n')
        lines.append("🤌🏻 Итог: {0}".format(str(all_data['remainder'])))

        text = "\n".join(lines)


        await call.message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="dds")]
            ]),
            parse_mode="Markdown"
        )
    except Exception as e:
        await call.message.answer(str(e))

@start_router.callback_query(lambda c: c.data.startswith("month:"))
async def show_month(call: types.CallbackQuery):
    try:
        await call.answer("Считаю аналитику ⏳")
        month_str = call.data.split(":", 1)[1]  # например "09.2024"

        await call.message.edit_text("📊 Считаю аналитику за месяц, подожди…")
        row = await sync_to_async(
            get_revenue_month_detail,
            thread_sensitive=False
        )(month_str)

        text = (
            f"📅 {row['Дата']}\n\n"
            f"Доход общий: {row['Доход общий']}\n"
            f"Моя метрика USD: {row['Моя метрика USD']}\n"
            f"Комиссия: {row['Комиссия']}\n"
            f"Моя метрика USDT: {row['Моя метрика USDT']}\n"
            f"Никита: {row['Никита']}\n"
            f"Доход ИП: {row['Доход ИП']}"
        )
        text = (
            f"📅 {row['Дата']}\n"
            f"💵 ДОХОД ОБЩИЙ: {row['Доход общий']}\n"
            f"├ БЕЗ КОНТРАГЕНТА {row['Без контрагента']}\n"
            f"└ ИП {row['Доход ИП']}"
        )

        await call.message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="analytics_months")]
            ]),
            parse_mode="Markdown"
        )
    except Exception as e:
        await call.message.answer(str(e))


@start_router.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(call: types.CallbackQuery):
    await call.message.edit_text(
        "Главное меню",
        reply_markup=menu_start()
    )
    await call.answer()