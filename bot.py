import asyncio
import logging
import os
import sys
import signal
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, URLInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.deep_linking import create_start_link, decode_payload

# ---------- НАСТРОЙКИ ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8862273506:AAHvSY7aLzmiTr_qnSLm10JzJWKey8TSfzU")
MASTER_ID = int(os.getenv("MASTER_ID", "8297446667"))

# Баннер
BANNER_URL = "https://i.imgur.com/ТВОЯ_ССЫЛКА_НА_БАННЕР.png"

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

# ---------- ТЕКСТЫ ----------
WELCOME_TEXT = (
    "💼 Добро пожаловать в  🤝\n\n"
    "⚡️ Ваш надёжный P2P-гарант:\n"
    "1⃣ Автоматические сделки с NFT и подарками\n"
    "2⃣ 🛡 Полная защита обеих сторон\n"
    "3⃣ 🪙 Реферальная программа — 50% от комиссии\n"
    "4⃣ 📦 Передача товаров через менеджера\n\n"
    "💡 Выберите действие ниже ⬇️"
)

ADMIN_TEXT = (
    "👑 Админ-панель\n\n"
    "Выберите действие:"
)

# ---------- FSM ----------
class DealStates(StatesGroup):
    waiting_role = State()
    waiting_currency = State()
    waiting_amount = State()
    waiting_second_party = State()

class AdminStates(StatesGroup):
    waiting_user_id = State()
    waiting_amount = State()
    waiting_deal_id = State()

# ---------- КЛАВИАТУРЫ ----------
def main_menu(lang="ru"):
    t = {
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
    }[lang]
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

def admin_menu():
    kb = [
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="admin_add_balance")],
        [InlineKeyboardButton(text="✅ Завершить сделку", callback_data="admin_complete_deal")],
        [InlineKeyboardButton(text="📋 Все сделки", callback_data="admin_all_deals")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔢 Создать тестовые сделки", callback_data="admin_fake_deals")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")]
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
        ("💎 TON", "ton"), ("💳 Карта", "card"), ("👤 Юзернейм", "username"),
        ("⭐ Звезды", "stars"), ("💵 USDT", "usdt"), ("₿ BTC", "btc")
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

def get_lang(uid):
    return users.get(uid, {}).get("lang", "ru")

# ---------- БАННЕР ----------
async def send_welcome_with_banner(chat_id, lang="ru"):
    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=URLInputFile(BANNER_URL),
            caption=WELCOME_TEXT,
            reply_markup=main_menu(lang)
        )
    except Exception as e:
        logging.warning(f"Баннер не загрузился: {e}")
        await bot.send_message(chat_id, WELCOME_TEXT, reply_markup=main_menu(lang))

async def edit_to_welcome_with_banner(call: CallbackQuery, lang="ru"):
    try:
        await call.message.edit_media(
            media=types.InputMediaPhoto(media=URLInputFile(BANNER_URL), caption=WELCOME_TEXT),
            reply_markup=main_menu(lang)
        )
    except:
        try:
            await call.message.delete()
        except:
            pass
        await send_welcome_with_banner(call.from_user.id, lang)

# ---------- КОМАНДЫ ----------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id
    args = message.text.split()
    referrer_id = None
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
        except:
            pass

    if uid not in users:
        users[uid] = {
            "balance": 0.0,
            "ton": "", "card": "", "username": "", "stars": "", "usdt": "", "btc": "",
            "lang": "ru",
            "history": [],
            "pending_rekv": None,
            "referrer_id": referrer_id,
            "referrals": []
        }
        # Начисление реферального бонуса
        if referrer_id and referrer_id != uid and referrer_id in users:
            users[referrer_id]["balance"] += 2.0
            users[referrer_id].setdefault("history", []).append(f"🎁 Реферальный бонус: +2₽ от пользователя {uid}")
            users[referrer_id].setdefault("referrals", []).append(uid)
            try:
                await bot.send_message(referrer_id, f"🎁 Вы получили 2₽ за приглашённого пользователя!")
            except:
                pass

    await send_welcome_with_banner(message.chat.id, get_lang(uid))

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != MASTER_ID:
        return await message.answer("❌ Нет доступа.")
    await message.answer(ADMIN_TEXT, reply_markup=admin_menu())

@dp.message(Command("masterb"))
async def master_balance(message: Message):
    if message.from_user.id != MASTER_ID:
        return await message.answer("❌ Нет доступа.")
    try:
        parts = message.text.split()
        if len(parts) != 3:
            raise ValueError
        uid = int(parts[1])
        amount = float(parts[2])
        if uid not in users:
            users[uid] = {"balance": 0.0, "history": []}
        users[uid]["balance"] += amount
        users[uid].setdefault("history", []).append(f"⚡ Зачисление: +{amount}")
        await message.answer(f"✅ Пользователю {uid} выдано {amount}₽.")
        try:
            await bot.send_message(uid, f"💰 На ваш баланс зачислено {amount}₽.")
        except:
            pass
    except:
        await message.answer("❌ Формат: /masterb user_id сумма")

@dp.message(Command("giveMas"))
async def complete_deal_cmd(message: Message):
    if message.from_user.id != MASTER_ID:
        return await message.answer("❌ Нет доступа.")
    try:
        _, deal_id_str = message.text.split()
        deal_id = int(deal_id_str)
        if deal_id not in deals or deals[deal_id]["status"] != "active":
            return await message.answer("❌ Сделка не найдена или уже завершена.")
        await complete_deal_logic(deal_id, message)
    except:
        await message.answer("❌ Формат: /giveMas deal_id")

async def complete_deal_logic(deal_id, message=None, call=None):
    deal = deals[deal_id]
    seller_id = deal["seller_id"]
    amount = deal["amount"]
    if seller_id in users:
        users[seller_id]["balance"] += amount
        users[seller_id].setdefault("history", []).append(f"✅ Сделка #{deal_id}: +{amount}₽")
    deal["status"] = "completed"
    text = f"✅ Сделка #{deal_id} завершена. Продавец получил {amount}₽."
    if message:
        await message.answer(text)
    if call:
        await call.message.edit_text(text, reply_markup=admin_menu())
    try:
        await bot.send_message(seller_id, f"✅ Сделка #{deal_id} завершена! Вам зачислено {amount}₽.")
        if deal["buyer_id"]:
            await bot.send_message(deal["buyer_id"], f"✅ Сделка #{deal_id} завершена.")
    except:
        pass

# ---------- ГЛАВНОЕ МЕНЮ ----------
@dp.callback_query(F.data == "main_menu")
async def show_main_menu(call: CallbackQuery):
    uid = call.from_user.id
    await edit_to_welcome_with_banner(call, get_lang(uid))

# ---------- АДМИН-ПАНЕЛЬ (CALLBACKS) ----------
@dp.callback_query(F.data == "admin_panel")
async def admin_panel_cb(call: CallbackQuery):
    if call.from_user.id != MASTER_ID:
        return await call.answer("❌ Нет доступа.", show_alert=True)
    await call.message.edit_text(ADMIN_TEXT, reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_add_balance")
async def admin_add_balance(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != MASTER_ID:
        return await call.answer("❌ Нет доступа.", show_alert=True)
    await call.message.edit_text("Введите ID пользователя и сумму через пробел:\nФормат: user_id сумма", reply_markup=back_button("ru"))
    await state.set_state(AdminStates.waiting_user_id)

@dp.message(AdminStates.waiting_user_id)
async def process_admin_balance(message: Message, state: FSMContext):
    if message.from_user.id != MASTER_ID:
        return
    try:
        uid_str, amount_str = message.text.split()
        uid = int(uid_str)
        amount = float(amount_str)
        if uid not in users:
            users[uid] = {"balance": 0.0, "history": []}
        users[uid]["balance"] += amount
        users[uid].setdefault("history", []).append(f"⚡ Админ: +{amount}₽")
        await message.answer(f"✅ Баланс пользователя {uid} пополнен на {amount}₽.", reply_markup=admin_menu())
        try:
            await bot.send_message(uid, f"💰 Администратор пополнил ваш баланс на {amount}₽.")
        except:
            pass
    except:
        await message.answer("❌ Неверный формат. Введите: user_id сумма")
    await state.clear()

@dp.callback_query(F.data == "admin_complete_deal")
async def admin_complete_deal(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != MASTER_ID:
        return await call.answer("❌ Нет доступа.", show_alert=True)
    await call.message.edit_text("Введите ID сделки для завершения:", reply_markup=back_button("ru"))
    await state.set_state(AdminStates.waiting_deal_id)

@dp.message(AdminStates.waiting_deal_id)
async def process_complete_deal(message: Message, state: FSMContext):
    if message.from_user.id != MASTER_ID:
        return
    try:
        deal_id = int(message.text.strip())
        if deal_id not in deals or deals[deal_id]["status"] != "active":
            return await message.answer("❌ Сделка не найдена или уже завершена.", reply_markup=admin_menu())
        await complete_deal_logic(deal_id, message=message)
    except:
        await message.answer("❌ Введите корректный ID сделки.")
    await state.clear()

@dp.callback_query(F.data == "admin_all_deals")
async def admin_all_deals(call: CallbackQuery):
    if call.from_user.id != MASTER_ID:
        return await call.answer("❌ Нет доступа.", show_alert=True)
    if not deals:
        return await call.message.edit_text("📭 Сделок нет.", reply_markup=admin_menu())
    text = "📋 Все сделки:\n\n" + "\n".join(
        [f"#{did}: {d['amount']} {d['currency']} | Продавец: {d['seller_id']} | Статус: {d['status']}" for did, d in deals.items()]
    )
    await call.message.edit_text(text, reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if call.from_user.id != MASTER_ID:
        return await call.answer("❌ Нет доступа.", show_alert=True)
    total_users = len(users)
    total_deals = len(deals)
    active_deals = sum(1 for d in deals.values() if d["status"] == "active")
    total_balance = sum(u.get("balance", 0) for u in users.values())
    text = (
        f"📊 Статистика:\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"📋 Всего сделок: {total_deals}\n"
        f"🟢 Активных сделок: {active_deals}\n"
        f"💰 Общий баланс: {total_balance}₽"
    )
    await call.message.edit_text(text, reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_fake_deals")
async def admin_fake_deals(call: CallbackQuery):
    if call.from_user.id != MASTER_ID:
        return await call.answer("❌ Нет доступа.", show_alert=True)
    global deal_counter
    count = random.randint(0, 40)
    currencies = ["ton", "card", "username", "stars", "usdt", "btc"]
    for _ in range(count):
        deal_counter += 1
        deals[deal_counter] = {
            "seller_id": MASTER_ID,
            "buyer_id": random.choice(list(users.keys())) if users else MASTER_ID,
            "amount": round(random.uniform(100, 10000), 2),
            "currency": random.choice(currencies),
            "status": random.choice(["active", "completed"])
        }
    await call.message.edit_text(f"✅ Создано {count} тестовых сделок.", reply_markup=admin_menu())

# ---------- БАЛАНС ----------
@dp.callback_query(F.data == "balance_menu")
async def bal_menu(call: CallbackQuery):
    uid = call.from_user.id
    lang = get_lang(uid)
    bal = users.get(uid, {}).get("balance", 0)
    text = f"💰 Ваш баланс: {bal:.2f}₽" if lang=="ru" else f"💰 Your balance: {bal:.2f}₽"
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
    users[uid]["balance"] = 0.0
    users[uid].setdefault("history", []).append(f"💸 Вывод: -{bal:.2f}₽")
    await call.message.edit_text(
        f"✅ Выведено {bal:.2f}₽\n\nОжидайте обработки менеджером." if lang=="ru" else f"✅ Withdrawn {bal:.2f}₽\n\nWait for manager processing.",
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

# ---------- СДЕЛКИ (ИСПРАВЛЕНО) ----------
@dp.callback_query(F.data == "new_deal")
async def new_deal(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Выберите роль:", reply_markup=deal_role_choice(get_lang(call.from_user.id)))
    await state.set_state(DealStates.waiting_role)

@dp.callback_query(F.data.startswith("role_"), DealStates.waiting_role)
async def role_chosen(call: CallbackQuery, state: FSMContext):
    role = "seller" if call.data == "role_seller" else "buyer"
    await state.update_data(role=role)
    await call.message.edit_text("Выберите валюту получения продавцом:", reply_markup=currency_choice(get_lang(call.from_user.id)))
    await state.set_state(DealStates.waiting_currency)

@dp.callback_query(F.data.startswith("cur_"), DealStates.waiting_currency)
async def currency_chosen(call: CallbackQuery, state: FSMContext):
    cur = call.data.replace("cur_", "")
    await state.update_data(currency=cur)
    await call.message.edit_text("Введите сумму сделки:", reply_markup=back_button(get_lang(call.from_user.id)))
    await state.set_state(DealStates.waiting_amount)

@dp.message(DealStates.waiting_amount)
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
    
    # Генерируем реферальную ссылку для второй стороны
    invite_link = f"https://t.me/{(await bot.me()).username}?start=deal_{deal_counter}"
    
    text = (
        f"✅ Сделка #{deal_counter} создана!\n\n"
        f"📋 Детали:\n"
        f"• Роль: {'Продавец' if role=='seller' else 'Покупатель'}\n"
        f"• Сумма: {amount} {data['currency']}\n"
        f"• Статус: Ожидает вторую сторону\n\n"
        f"🔗 Отправьте эту ссылку второй стороне для входа в сделку:\n"
        f"{invite_link}\n\n"
        f"Ожидайте подтверждения от менеджера."
    )
    await message.answer(text, reply_markup=main_menu(lang))
    await state.clear()

# Обработка входа второй стороны по ссылке сделки
@dp.message(Command("start"))
async def cmd_start_deal(message: Message):
    uid = message.from_user.id
    args = message.text.split()
    
    if len(args) > 1 and args[1].startswith("deal_"):
        try:
            deal_id = int(args[1].split("_")[1])
            if deal_id in deals and deals[deal_id]["status"] == "active":
                deal = deals[deal_id]
                if deal["seller_id"] is None:
                    deals[deal_id]["seller_id"] = uid
                elif deal["buyer_id"] is None:
                    deals[deal_id]["buyer_id"] = uid
                else:
                    return await message.answer("❌ Эта сделка уже заполнена.")
                
                await message.answer(
                    f"✅ Вы присоединились к сделке #{deal_id}!\n"
                    f"Сумма: {deal['amount']} {deal['currency']}\n"
                    f"Ожидайте завершения от менеджера.",
                    reply_markup=main_menu(get_lang(uid))
                )
                return
        except:
            pass
    
    # Обычный старт (рефералы)
    await cmd_start(message)

# ---------- МОИ СДЕЛКИ ----------
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
    try:
        _, deal_id_str = message.text.split()
        deal_id = int(deal_id_str)
        deal = deals.get(deal_id)
        if not deal or (deal["seller_id"] != uid and deal["buyer_id"] != uid and message.from_user.id != MASTER_ID):
            return await message.answer("❌ Сделка не найдена.")
        await message.answer(f"🔍 Сделка #{deal_id}:\nСумма: {deal['amount']} {deal['currency']}\nСтатус: {deal['status']}")
    except:
        await message.answer("❌ Формат: /search код_сделки")

# ---------- РЕФЕРАЛЫ ----------
@dp.callback_query(F.data == "referrals")
async def referrals(call: CallbackQuery):
    uid = call.from_user.id
    lang = get_lang(uid)
    refs = users.get(uid, {}).get("referrals", [])
    ref_link = f"https://t.me/{(await bot.me()).username}?start={uid}"
    text = (
        f"👥 Реферальная программа\n\n"
        f"За каждого приглашённого друга — 2₽ на баланс!\n\n"
        f"🔗 Ваша ссылка:\n{ref_link}\n\n"
        f"👤 Приглашено: {len(refs)} чел.\n"
        f"💰 Заработано: {len(refs) * 2}₽"
    ) if lang=="ru" else (
        f"👥 Referral Program\n\n"
        f"2₽ for each invited friend!\n\n"
        f"🔗 Your link:\n{ref_link}\n\n"
        f"👤 Invited: {len(refs)} people\n"
        f"💰 Earned: {len(refs) * 2}₽"
    )
    await call.message.edit_text(text, reply_markup=back_button(lang))

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
    text = (
        "🆘 Техподдержка\n\n"
        "Свяжитесь с менеджером: @dumufa"
    ) if lang=="ru" else (
        "🆘 Support\n\n"
        "Contact manager: @dumufa"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать в поддержку", url="https://t.me/dumufa")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

# ---------- ЗАПУСК ----------
async def main():
    logging.info("Закрываю старые сессии...")
    try:
        await bot.session.close()
    except:
        pass
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Запускаю поллинг...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), polling_timeout=20, handle_as_tasks=True)

if __name__ == "__main__":
    def signal_handler(sig, frame):
        print("\nВыключение...")
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    asyncio.run(main())
