import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

# ---------- НАСТРОЙКИ ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8862273506:AAEmA-xWmihELm0oajcvkaxkI_Rbr2kRppw")
MASTER_ID = int(os.getenv("MASTER_ID", "8297446667"))

# Временное хранилище
users = {}
deals = {}
deal_counter = 1000

# Логи
logging.basicConfig(level=logging.INFO)

# Бот и диспетчер
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ---------- FSM ----------
class DealStates(StatesGroup):
    choosing_role = State()
    choosing_currency = State()
    entering_amount = State()

class RekvStates(StatesGroup):
    waiting_input = State()

# ---------- КЛАВИАТУРЫ ----------
def main_menu(lang="ru"):
    texts = {
        "ru": {
            "balance": "💰 Баланс",
            "my_deals": "📋 Мои сделки",
            "new_deal": "🤝 Создать сделку",
            "my_rekv": "📄 Мои реквизиты",
            "referrals": "👥 Рефералы",
            "lang": "🌐 Язык / Language",
            "support": "🆘 Техподдержка"
        },
        "en": {
            "balance": "💰 Balance",
            "my_deals": "📋 My Deals",
            "new_deal": "🤝 New Deal",
            "my_rekv": "📄 My Details",
            "referrals": "👥 Referrals",
            "lang": "🌐 Language / Язык",
            "support": "🆘 Support"
        }
    }
    t = texts[lang]
    kb = [
        [InlineKeyboardButton(text=t["balance"], callback_data="balance_menu")],
        [InlineKeyboardButton(text=t["my_deals"], callback_data="my_deals"),
         InlineKeyboardButton(text=t["new_deal"], callback_data="new_deal")],
        [InlineKeyboardButton(text=t["my_rekv"], callback_data="my_rekv")],
        [InlineKeyboardButton(text=t["referrals"], callback_data="referrals")],
        [InlineKeyboardButton(text=t["lang"], callback_data="change_lang"),
         InlineKeyboardButton(text=t["support"], callback_data="support")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def balance_menu(lang="ru"):
    t = {
        "ru": {"history": "📜 История транзакций", "withdraw": "💸 Вывод средств", "back": "🔙 Назад"},
        "en": {"history": "📜 Transaction History", "withdraw": "💸 Withdraw", "back": "🔙 Back"}
    }[lang]
    kb = [
        [InlineKeyboardButton(text=t["history"], callback_data="tx_history")],
        [InlineKeyboardButton(text=t["withdraw"], callback_data="withdraw_funds")],
        [InlineKeyboardButton(text=t["back"], callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def rekv_menu(lang="ru"):
    t = {
        "ru": ["💎 TON Кошелек", "💳 Карта", "👤 Юзернейм", "⭐ Звезды", "💵 USDT Кошелек", "₿ BTC Кошелек", "🔙 Назад"],
        "en": ["💎 TON Wallet", "💳 Card", "👤 Username", "⭐ Stars", "💵 USDT Wallet", "₿ BTC Wallet", "🔙 Back"]
    }[lang]
    kb = [
        [InlineKeyboardButton(text=t[0], callback_data="set_ton")],
        [InlineKeyboardButton(text=t[1], callback_data="set_card")],
        [InlineKeyboardButton(text=t[2], callback_data="set_username")],
        [InlineKeyboardButton(text=t[3], callback_data="set_stars")],
        [InlineKeyboardButton(text=t[4], callback_data="set_usdt")],
        [InlineKeyboardButton(text=t[5], callback_data="set_btc")],
        [InlineKeyboardButton(text=t[6], callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def deal_role_choice(lang="ru"):
    t = {
        "ru": ["🛒 Я продавец", "🛍 Я покупатель", "🔙 Отмена"],
        "en": ["🛒 I'm Seller", "🛍 I'm Buyer", "🔙 Cancel"]
    }[lang]
    kb = [
        [InlineKeyboardButton(text=t[0], callback_data="role_seller")],
        [InlineKeyboardButton(text=t[1], callback_data="role_buyer")],
        [InlineKeyboardButton(text=t[2], callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def currency_choice(lang="ru"):
    currencies = [
        ("💎 TON", "ton"),
        ("💳 Карта", "card"),
        ("👤 Юзернейм", "username"),
        ("⭐ Звезды", "stars"),
        ("💵 USDT", "usdt"),
        ("₿ BTC", "btc")
    ]
    kb = []
    for i in range(0, len(currencies), 2):
        row = [InlineKeyboardButton(text=currencies[i][0], callback_data=f"cur_{currencies[i][1]}")]
        if i+1 < len(currencies):
            row.append(InlineKeyboardButton(text=currencies[i+1][0], callback_data=f"cur_{currencies[i+1][1]}"))
        kb.append(row)
    kb.append([InlineKeyboardButton(text="🔙 Отмена" if lang=="ru" else "🔙 Cancel", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def back_button(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад" if lang=="ru" else "🔙 Back", callback_data="main_menu")]
    ])

# ---------- ПОЛУЧЕНИЕ ЯЗЫКА ----------
def get_lang(uid):
    return users.get(uid, {}).get("lang", "ru")

# ---------- КОМАНДЫ ----------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id
    if uid not in users:
        users[uid] = {
            "balance": 0.0,
            "ton": "", "card": "", "username": "", "stars": "", "usdt": "", "btc": "",
            "lang": "ru",
            "history": [],
            "pending_rekv": None
        }
    await message.answer(
        "💼 Добро пожаловать в  🤝\n\n"
        "⚡️ Ваш надёжный P2P-гарант:\n"
        "1⃣ Автоматические сделки с NFT и подарками\n"
        "2⃣ 🛡 Полная защита обеих сторон\n"
        "3⃣ 🪙 Реферальная программа — 50% от комиссии\n"
        "4⃣ 📦 Передача товаров через менеджера\n\n"
        "💡 Выберите действие ниже ⬇️",
        reply_markup=main_menu(get_lang(uid))
    )

@dp.message(Command("masterb"))
async def master_balance(message: Message):
    if message.from_user.id != MASTER_ID:
        return await message.answer("❌ Нет доступа.")
    try:
        _, uid_str, amount_str = message.text.split()
        uid = int(uid_str)
        amount = float(amount_str)
        if uid not in users:
            users[uid] = {"balance": 0.0, "history": []}
        users[uid]["balance"] += amount
        users[uid].setdefault("history", []).append(f"⚡ Зачисление: +{amount}")
        await message.answer(f"✅ Пользователю {uid} выдано {amount}.")
        try:
            await bot.send_message(uid, f"💰 На ваш баланс зачислено {amount}.")
        except:
            pass
    except:
        await message.answer("❌ Формат: /masterb user_id сумма")

@dp.message(Command("giveMas"))
async def complete_deal(message: Message):
    if message.from_user.id != MASTER_ID:
        return await message.answer("❌ Нет доступа.")
    try:
        _, deal_id_str = message.text.split()
        deal_id = int(deal_id_str)
        if deal_id not in deals or deals[deal_id]["status"] != "active":
            return await message.answer("❌ Сделка не найдена или уже завершена.")
        deal = deals[deal_id]
        seller_id = deal["seller_id"]
        amount = deal["amount"]
        users[seller_id]["balance"] += amount
        users[seller_id].setdefault("history", []).append(f"✅ Сделка #{deal_id}: +{amount}")
        deal["status"] = "completed"
        await message.answer(f"✅ Сделка #{deal_id} завершена. Продавец получил {amount}.")
        try:
            await bot.send_message(seller_id, f"✅ Сделка #{deal_id} завершена! Вам зачислено {amount}.")
            await bot.send_message(deal["buyer_id"], f"✅ Сделка #{deal_id} завершена.")
        except:
            pass
    except:
        await message.answer("❌ Формат: /giveMas deal_id")

# ---------- ГЛАВНОЕ МЕНЮ ----------
@dp.callback_query(F.data == "main_menu")
async def show_main_menu(call: CallbackQuery):
    uid = call.from_user.id
    await call.message.edit_text("💼 Главное меню\n\n💡 Выберите действие:", reply_markup=main_menu(get_lang(uid)))

# ---------- БАЛАНС ----------
@dp.callback_query(F.data == "balance_menu")
async def bal_menu(call: CallbackQuery):
    uid = call.from_user.id
    lang = get_lang(uid)
    bal = users.get(uid, {}).get("balance", 0)
    text = f"💰 Ваш баланс: {bal:.2f}" if lang=="ru" else f"💰 Your balance: {bal:.2f}"
    await call.message.edit_text(text, reply_markup=balance_menu(lang))

@dp.callback_query(F.data == "tx_history")
async def tx_history(call: CallbackQuery):
    uid = call.from_user.id
    lang = get_lang(uid)
    hist = users.get(uid, {}).get("history", [])
    if not hist:
        t = "📭 История пуста" if lang=="ru" else "📭 No transactions"
        await call.message.edit_text(t, reply_markup=back_button(lang))
    else:
        text = "\n".join(hist[-15:])
        await call.message.edit_text(f"📜 История операций:\n{text}", reply_markup=back_button(lang))

@dp.callback_query(F.data == "withdraw_funds")
async def withdraw_funds(call: CallbackQuery):
    uid = call.from_user.id
    lang = get_lang(uid)
    bal = users.get(uid, {}).get("balance", 0)
    if bal <= 0:
        await call.answer("❌ Недостаточно средств" if lang=="ru" else "❌ Insufficient funds", show_alert=True)
        return
    # Визуальный вывод (списываем с баланса)
    users[uid]["balance"] = 0.0
    users[uid].setdefault("history", []).append(f"💸 Вывод: -{bal:.2f}")
    await call.message.edit_text(
        f"✅ Выведено {bal:.2f}\n\nОжидайте обработки менеджером." if lang=="ru" else f"✅ Withdrawn {bal:.2f}\n\nWait for manager processing.",
        reply_markup=back_button(lang)
    )

# ---------- МОИ РЕКВИЗИТЫ ----------
@dp.callback_query(F.data == "my_rekv")
async def my_rekv(call: CallbackQuery):
    uid = call.from_user.id
    lang = get_lang(uid)
    u = users.get(uid, {})
    info = []
    labels = {
        "ton": "💎 TON", "card": "💳 Карта", "username": "👤 Юзернейм",
        "stars": "⭐ Звезды", "usdt": "💵 USDT", "btc": "₿ BTC"
    }
    for k, v in labels.items():
        val = u.get(k, "")
        info.append(f"{v}: {val if val else '❌ не указан' if lang=='ru' else '❌ not set'}")
    await call.message.edit_text("\n".join(info), reply_markup=rekv_menu(lang))

for cb, key in [
    ("set_ton", "ton"), ("set_card", "card"), ("set_username", "username"),
    ("set_stars", "stars"), ("set_usdt", "usdt"), ("set_btc", "btc")
]:
    @dp.callback_query(F.data == cb)
    async def ask_rekv(call: CallbackQuery, key=key):
        uid = call.from_user.id
        lang = get_lang(uid)
        prompts = {
            "ton": ("Введите TON кошелёк:", "Enter TON wallet:"),
            "card": ("Введите номер карты:", "Enter card number:"),
            "username": ("Введите юзернейм:", "Enter username:"),
            "stars": ("Введите ID звёзд:", "Enter Stars ID:"),
            "usdt": ("Введите USDT кошелёк:", "Enter USDT wallet:"),
            "btc": ("Введите BTC кошелёк:", "Enter BTC wallet:")
        }
        prompt = prompts[key][0] if lang=="ru" else prompts[key][1]
        users[uid]["pending_rekv"] = key
        await call.message.edit_text(prompt, reply_markup=back_button(lang))

@dp.message()
async def handle_rekv_input(message: Message):
    uid = message.from_user.id
    if uid in users and users[uid].get("pending_rekv"):
        key = users[uid]["pending_rekv"]
        users[uid][key] = message.text
        users[uid]["pending_rekv"] = None
        lang = get_lang(uid)
        await message.answer("✅ Сохранено!" if lang=="ru" else "✅ Saved!", reply_markup=main_menu(lang))
    # Если нет ожидания — игнорируем (или можно добавить обработку суммы для сделки)

# ---------- СДЕЛКИ ----------
@dp.callback_query(F.data == "new_deal")
async def new_deal(call: CallbackQuery, state: FSMContext):
    await state.set_state(DealStates.choosing_role)
    await call.message.edit_text("Выберите роль:", reply_markup=deal_role_choice(get_lang(call.from_user.id)))

@dp.callback_query(F.data.startswith("role_"), DealStates.choosing_role)
async def role_chosen(call: CallbackQuery, state: FSMContext):
    role = "seller" if call.data == "role_seller" else "buyer"
    await state.update_data(role=role)
    await call.message.edit_text("Выберите валюту получения продавцом:", reply_markup=currency_choice(get_lang(call.from_user.id)))
    await state.set_state(DealStates.choosing_currency)

@dp.callback_query(F.data.startswith("cur_"), DealStates.choosing_currency)
async def currency_chosen(call: CallbackQuery, state: FSMContext):
    cur = call.data.replace("cur_", "")
    await state.update_data(currency=cur)
    await call.message.edit_text("Введите сумму:", reply_markup=back_button(get_lang(call.from_user.id)))
    await state.set_state(DealStates.entering_amount)

@dp.message(DealStates.entering_amount)
async def amount_entered(message: Message, state: FSMContext):
    global deal_counter
    uid = message.from_user.id
    lang = get_lang(uid)
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
    except:
        return await message.answer("❌ Введите корректное число.")
    data = await state.get_data()
    deal_counter += 1
    role = data["role"]
    deals[deal_counter] = {
        "seller_id": uid if role == "seller" else None,
        "buyer_id": uid if role == "buyer" else None,
        "amount": amount,
        "currency": data["currency"],
        "status": "active"
    }
    text = (f"✅ Сделка #{deal_counter} создана!\n"
            f"Роль: {'Продавец' if role=='seller' else 'Покупатель'}\n"
            f"Сумма: {amount} {data['currency']}\n"
            f"Ожидайте действий менеджера.")
    await message.answer(text, reply_markup=main_menu(lang))
    await state.clear()

@dp.callback_query(F.data == "my_deals")
async def my_deals(call: CallbackQuery):
    uid = call.from_user.id
    lang = get_lang(uid)
    user_deals = [(did, d) for did, d in deals.items() if d["seller_id"]==uid or d["buyer_id"]==uid]
    if not user_deals:
        await call.message.edit_text("🔍 Сделок нет." if lang=="ru" else "🔍 No deals.", reply_markup=back_button(lang))
        return
    text = "📋 Ваши сделки:\n\n" + "\n".join(
        [f"🔹 #{did}: {d['amount']} {d['currency']} | Статус: {d['status']}" for did, d in user_deals]
    )
    text += "\n\n🔎 Поиск: /search код_сделки"
    await call.message.edit_text(text, reply_markup=back_button(lang))

@dp.message(Command("search"))
async def search_deal(message: Message):
    uid = message.from_user.id
    lang = get_lang(uid)
    try:
        _, deal_id_str = message.text.split()
        deal_id = int(deal_id_str)
        deal = deals.get(deal_id)
        if not deal or (deal["seller_id"] != uid and deal["buyer_id"] != uid):
            return await message.answer("❌ Сделка не найдена.")
        await message.answer(f"🔍 Сделка #{deal_id}:\nСумма: {deal['amount']} {deal['currency']}\nСтатус: {deal['status']}")
    except:
        await message.answer("❌ Формат: /search код_сделки")

# ---------- РЕФЕРАЛЫ ----------
@dp.callback_query(F.data == "referrals")
async def referrals(call: CallbackQuery):
    lang = get_lang(call.from_user.id)
    await call.message.edit_text("🚧 В разработке" if lang=="ru" else "🚧 In development", reply_markup=back_button(lang))

# ---------- ЯЗЫК ----------
@dp.callback_query(F.data == "change_lang")
async def change_lang(call: CallbackQuery):
    uid = call.from_user.id
    cur = users.setdefault(uid, {}).setdefault("lang", "ru")
    new_lang = "en" if cur == "ru" else "ru"
    users[uid]["lang"] = new_lang
    await call.message.edit_text("🌐 Язык изменён!" if new_lang=="ru" else "🌐 Language changed!", reply_markup=main_menu(new_lang))

# ---------- ТЕХПОДДЕРЖКА ----------
@dp.callback_query(F.data == "support")
async def support(call: CallbackQuery):
    lang = get_lang(call.from_user.id)
    await call.message.edit_text("🆘 Техподдержка: скоро здесь будут контакты менеджера.", reply_markup=back_button(lang))

# ---------- ЗАПУСК ----------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
