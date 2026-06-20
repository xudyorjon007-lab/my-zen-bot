import asyncio
import logging
import sqlite3
import threading
import http.server
import socketserver
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, \
    CallbackQuery

# --- SOZLAMALAR ---
BOT_TOKEN = "8904307795:AAGipj9PJzimAu8bzxypDTLqiYaqHAsiXHI"
ADMIN_ID = 7578712290  # O'zingizning Telegram ID-ingiz
PREMIUM_PRICE = 80000  # Premium status narxi (so'mda)
KARTA_RAQAM = "5440 8103 1635 5816"  # Bu yerga o'zingizning karta raqamingizni yozing!
KARTA_EGA_SMI = "Nishanova Umida."  # Bu yerga kartangiz egasining ismini yozing!

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# --- MA'LUMOTLAR BAZASI (SQLITE) ---
def init_db():
    conn = sqlite3.connect("referral_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            balance REAL DEFAULT 0.0,
            referred_by INTEGER DEFAULT NULL,
            is_premium INTEGER DEFAULT 0,
            click_count INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY,
            amount REAL,
            is_used INTEGER DEFAULT 0
        )
    """)
    conn.commit()

    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if "is_premium" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_premium INTEGER DEFAULT 0")
    if "click_count" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN click_count INTEGER DEFAULT 0")
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = sqlite3.connect("referral_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user


def register_user(user_id, full_name, referrer_id=None):
    conn = sqlite3.connect("referral_bot.db")
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (user_id, full_name, referred_by) VALUES (?, ?, ?)",
            (user_id, full_name, referrer_id)
        )
        conn.commit()

        if referrer_id:
            referrer = get_user(referrer_id)
            if referrer:
                bonus = 300 if len(referrer) > 4 and referrer[4] == 1 else 100
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bonus, referrer_id))
                conn.commit()
                return bonus
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()
    return 0


def set_premium(user_id, status=1):
    """Foydalanuvchiga premium berish (status=1) yoki olib qo'yish (status=0)"""
    conn = sqlite3.connect("referral_bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_premium = ? WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()


def get_premium_users():
    """Barcha premium foydalanuvchilarni bazadan olish"""
    conn = sqlite3.connect("referral_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, full_name FROM users WHERE is_premium = 1")
    users = cursor.fetchall()
    conn.close()
    return users


def add_promocode(code, amount):
    conn = sqlite3.connect("referral_bot.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO promocodes (code, amount) VALUES (?, ?)", (code.upper(), amount))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def use_promocode_db(user_id, code):
    conn = sqlite3.connect("referral_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM promocodes WHERE code = ? AND is_used = 0", (code.upper(),))
    promo = cursor.fetchone()

    if promo:
        amount = promo[1]
        cursor.execute("UPDATE promocodes SET is_used = 1 WHERE code = ?", (code.upper(),))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        conn.close()
        return amount
    conn.close()
    return None


def increment_click(user_id):
    conn = sqlite3.connect("referral_bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET click_count = click_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_all_users_stats():
    conn = sqlite3.connect("referral_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
    premium = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 0")
    normal = cursor.fetchone()[0]
    conn.close()
    return total, premium, normal


def get_all_user_ids():
    conn = sqlite3.connect("referral_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return ids


# --- KLAVIATURALAR ---
def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Mening balansim"), KeyboardButton(text="🔗 Taklifnoma (Link)")],
            [KeyboardButton(text="💎 Premium Xizmatlar"), KeyboardButton(text="🎟 Promokod Kiritish")],
            [KeyboardButton(text="📊 Statistika")]
        ],
        resize_keyboard=True
    )


def admin_keyboard():
    """Faqat admin ko'ra oladigan inline menyu"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Premium maqomni qaytarib olish", callback_data="admin_revoke_premium")],
        [InlineKeyboardButton(text="📊 Umumiy Statistika", callback_data="admin_stats")]
    ])


# --- HANDLERLAR ---

@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    full_name = message.from_user.full_name

    args = message.text.split()
    referrer_id = None

    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
        if referrer_id == user_id:
            referrer_id = None

    user_exists = get_user(user_id)

    if not user_exists:
        bonus_given = register_user(user_id, full_name, referrer_id)
        if bonus_given > 0 and referrer_id:
            try:
                await bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎉 Tabriklaymiz! Do'stingiz {full_name} kirdi. Balansingizga {bonus_given} so'm qo'shildi!"
                )
            except Exception:
                pass
        await message.answer(
            f"👋 Salom {full_name}! Botimizga xush kelibsiz. Do'stlashtirish tizimi orqali pul ishlang!",
            reply_markup=main_keyboard())
    else:
        await message.answer(f"Siz allaqachon ro'yxatdan o'tgansiz. Menyudan foydalaning:",
                             reply_markup=main_keyboard())


# --- ADMIN PANEL BUYRUG'I ---
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Bu buyruq faqat bot admini uchun mo'ljallangan!")
        return
    await message.answer("🛠 **Boshqaruv Paneli:**\nQuyidagi funksiyalardan birini tanlang:",
                         reply_markup=admin_keyboard())


# --- PREMIUM O'CHIRISH FUNKSIYASI ---
@dp.callback_query(F.data == "admin_revoke_premium")
async def admin_revoke_list(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    premium_users = get_premium_users()
    if not premium_users:
        await call.message.answer("ℹ️ Botda hozircha hech qanday Premium foydalanuvchi yo'q.")
        await call.answer()
        return

    # Har bir foydalanuvchi uchun tugma yaratamiz
    buttons = []
    for u_id, name in premium_users:
        buttons.append([InlineKeyboardButton(text=f"❌ {name} (ID: {u_id})", callback_data=f"remove_prem_{u_id}")])

    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await call.message.answer(
        "👤 **Premium maqomga ega foydalanuvchilar:**\nMaqomni o'chirish uchun kerakli odamning ustiga bosing:",
        reply_markup=markup)
    await call.answer()


@dp.callback_query(F.data.startswith("remove_prem_"))
async def process_remove_premium(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    target_id = int(call.data.split("_")[2])
    user_info = get_user(target_id)

    if user_info:
        name = user_info[1]
        set_premium(target_id, status=0)  # Premium maqomini 0 (oddiy) qilamiz

        # Foydalanuvchining o'ziga xabar yuborish
        try:
            await bot.send_message(
                chat_id=target_id,
                text="⚠️ **Diqqat!** Sizning Premium maqomingiz admin tomonidan bekor qilindi (sohta chek yoki qoidabuzarlik sababli). Savollaringiz bo'lsa adminga murojaat qiling."
            )
        except Exception:
            pass

        await call.message.edit_text(
            text=f"🟢 `{name}` (ID: `{target_id}`) dan Premium maqomi muvaffaqiyatli olib qo'yildi va unga ogohlantirish yuborildi.")
    else:
        await call.message.answer("Xatolik: Foydalanuvchi topilmadi.")

    await call.answer("Premium bekor qilindi!", show_alert=True)


@dp.callback_query(F.data == "admin_stats")
async def admin_show_stats(call: CallbackQuery):
    total, premium, normal = get_all_users_stats()
    await call.message.answer(
        f"📊 **Batafsil Statistika:**\n\n"
        f"👥 Hamma foydalanuvchilar: {total} ta\n"
        f"⚪ Oddiy foydalanuvchilar: {normal} ta\n"
        f"💎 Premium foydalanuvchilar: {premium} ta"
    )
    await call.answer()


@dp.message(F.text == "💰 Mening balansim")
async def check_balance(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        return

    balance = user[2]
    is_premium = user[4] if len(user) > 4 else 0
    clicks = user[5] if len(user) > 5 else 0

    if is_premium == 0 and clicks >= 3:
        await message.answer(
            "⚠️ **Kunlik limit tugadi!**\n\n"
            "Oddiy foydalanuvchilar balansni kuniga faqat 3 marta tekshira oladi.\n"
            "Cheksiz foydalanish uchun 💎 **Premium Xizmatlar** bo'limiga o'ting!"
        )
        return

    if is_premium == 0:
        increment_click(message.from_user.id)

    status_text = "💎 Premium" if is_premium == 1 else "⚪ Oddiy Foydalanuvchi"

    await message.answer(
        f"👤 **Sizning maqomingiz:** {status_text}\n"
        f"💵 **Sizning balansingiz:** {balance} so'm\n\n"
        f"💡 Pul chiqarish minimal miqdori: 50,000 so'm.\n"
        f"Pulni yechish uchun adminga yozing: t.me/murod_9992"
    )


@dp.message(F.text == "🔗 Taklifnoma (Link)")
async def get_link(message: Message):
    user = get_user(message.from_user.id)
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"

    is_premium = user[4] if user and len(user) > 4 else 0
    reward = "300 so'm (Premium bonus! 🔥)" if is_premium == 1 else "100 so'm"

    await message.answer(
        f"🤝 **Sizning shaxsiy taklifnoma havolangiz:**\n\n`{ref_link}`\n\n"
        f"Ushbu linkni do'stlaringizga tarqating. Siz hozirgi statusingizda har bir do'stingiz uchun **{reward}** olasiz!"
    )


@dp.message(F.text == "💎 Premium Xizmatlar")
async def premium_features(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        return

    is_premium = user[4] if len(user) > 4 else 0

    if is_premium == 0:
        pay_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Karta raqamni olish", callback_data="get_card")],
            [InlineKeyboardButton(text="✅ To'lov qildim (Chek yuborish)", callback_data="send_check")]
        ])

        await message.answer(
            f"🌟 **💎 PREMIUM REJIM AFZALLIKLARI:**\n\n"
            f"1️⃣ Takliflar uchun **3 baravar ko'p (300 so'm)** olasiz!\n"
            f"2️⃣ Botdagi barcha kunlik cheklovlar butunlay olib tashlanadi.\n"
            f"3️⃣ Eksklyuziv pullik kinolar va IT darsliklar kanaliga kirish.\n\n"
            f"💰 **Premium narxi:** {PREMIUM_PRICE} so'm.\n\n"
            f"Sotib olish uchun quyidagi tugmalardan foydalaning:",
            reply_markup=pay_keyboard
        )
    else:
        await message.answer(
            "👑 **PREMIUM KLUBSA XUSH KELIBSIZ!**\n\n"
            "🎬 **1. Maxsus Pullik Kinolar:** t.me/Yopiq_Kino_Kanalimiz_Link\n"
            "📚 **2. Pullik IT Darsliklar:** t.me/Yopiq_Kurs_Kanalimiz_Link\n"
            "🤖 **3. VIP Aloqa xonasi ochildi.**"
        )


@dp.callback_query(F.data == "get_card")
async def callback_get_card(call: CallbackQuery):
    await call.message.answer(
        f"💳 **To'lov uchun karta ma'lumotlari:**\n\n"
        f"📌 Karta raqam: `{KARTA_RAQAM}`\n"
        f"👤 Egasi: {KARTA_EGA_SMI}\n"
        f"💵 Summa: {PREMIUM_PRICE} so'm\n\n"
        f"⚠️ To'lovni amalga oshirgach, chekni (skrinshotni) adminga yuborish uchun **'To'lov qildim'** tugmasini bosing."
    )
    await call.answer()


@dp.callback_query(F.data == "send_check")
async def callback_send_check(call: CallbackQuery):
    await call.message.answer(
        "📥 Iltimos, to'lov chekini (skrinshotini) menga **rasm shaklida** yuboring. Men uni tasdiqlash uchun adminga yetkazaman.")
    await call.answer()


@dp.message(F.photo)
async def handle_receipt(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)

    if user and len(user) > 4 and user[4] == 1:
        await message.answer("Siz allaqachon Premiumsiz!")
        return

    admin_keyboard_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash (Premium qilish)", callback_data=f"accept_{user_id}")],
        [InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{user_id}")]
    ])

    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=message.photo[-1].file_id,
        caption=f"🔔 **Yangi Premium To'lov cheki!**\n\n👤 Kimdan: {message.from_user.full_name}\n🆔 ID: `{user_id}`",
        reply_markup=admin_keyboard_markup
    )
    await message.answer("✅ Chekingiz adminga tekshirish uchun yuborildi. Tez orada maqomingiz yangilanadi!")


@dp.callback_query(F.data.startswith("accept_"))
async def admin_accept_pay(call: CallbackQuery):
    target_user_id = int(call.data.split("_")[1])
    set_premium(target_user_id, status=1)

    try:
        await bot.send_message(
            chat_id=target_user_id,
            text="🎉 **Xushxabar!** Admin to'lovingizni tasdiqladi. Maqomingiz **💎 PREMIUM** ga yangilandi! Barcha imkoniyatlar ochildi. 🔥"
        )
    except Exception:
        pass

    await call.message.edit_caption(caption=call.message.caption + "\n\n🟢 **TASDIQLANDI (Premium berildi)**")
    await call.answer("Tasdiqlandi!", show_alert=True)


@dp.callback_query(F.data.startswith("reject_"))
async def admin_reject_pay(call: CallbackQuery):
    target_user_id = int(call.data.split("_")[1])
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text="❌ **To'lovingiz rad etildi.**\nChek noto'g'ri yoki pul kelib tushmagan bo'lishi mumkin. Muammo bo'lsa, adminga yozing."
        )
    except Exception:
        pass
    await call.message.edit_caption(caption=call.message.caption + "\n\n🔴 **RAD ETILDI**")
    await call.answer("Rad etildi!", show_alert=True)


# --- PROMOKOD TIZIMI ---
@dp.message(F.text == "🎟 Promokod Kiritish")
async def promo_enter_request(message: Message):
    await message.answer("🔑 **Promokodingizni yozib yuboring:**\n\n(Masalan: OTM_PROMO )")


@dp.message(F.text & ~F.text.startswith("/"))
async def check_promocode_handler(message: Message):
    user_id = message.from_user.id
    code_text = message.text.strip()

    if code_text in ["💰 Mening balansim", "🔗 Taklifnoma (Link)", "💎 Premium Xizmatlar", "🎟 Promokod Kiritish",
                     "📊 Statistika"]:
        return

    amount = use_promocode_db(user_id, code_text)
    if amount:
        await message.answer(
            f"🎉 **Ajoyib!** Promokod muvaffaqiyatli ishlatildi. Balansingizga **{amount} so'm** qo'shildi! 💸")
    else:
        await message.answer("❌ **Xato promokod!**\nPromokod eskirgan, xato yozilgan yoki allaqachon ishlatilgan.")


@dp.message(F.text.startswith("/yangi_promo"))
async def create_promocode(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    args = message.text.split()
    if len(args) < 3:
        await message.answer("Xato! Foydalanish: `/yangi_promo KOD_NOMI SUMMA`")
        return

    code_name = args[1].upper()
    try:
        amount = float(args[2])
    except ValueError:
        await message.answer("Summa faqat raqamlarda bo'lishi kerak!")
        return

    success = add_promocode(code_name, amount)
    if success:
        await message.answer(f"✅ Yangi promokod yaratildi:\n🔑 Kod: `{code_name}`\n💰 Qiymati: {amount} so'm")
    else:
        await message.answer("❌ Bu nomdagi promokod allaqachon mavjud!")


@dp.message(F.text == "📊 Statistika")
async def show_stats(message: Message):
    try:
        total, premium, normal = get_all_users_stats()
        await message.answer(
            f"📊 **BOTNING REAL VAQTDAGI STATISTIKASI**\n\n"
            f"👥 **Umumiy foydalanuvchilar:** {total} ta\n"
            f"⚪ **Oddiy foydalanuvchilar:** {normal} ta\n"
            f"💎 **Premium foydalanuvchilar:** {premium} ta\n\n"
            f"⚡ _Statistika avtomatik tarzda yangilanadi._"
        )
    except Exception as e:
        logging.error(f"Statistikada xato: {e}")
        await message.answer("❌ Statistikani yuklashda xatolik yuz berdi. Iltimos bazani tekshiring.")


@dp.message(F.text.startswith("/reklama"))
async def send_global_ad(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    ad_text = message.text.replace("/reklama", "").strip()
    if not ad_text:
        await message.answer("Xato! Foydalanish: `/reklama Reklama matni`")
        return

    await message.answer("📢 Reklama barcha foydalanuvchilarga tarqatilmoqda...")

    user_ids = get_all_user_ids()
    success = 0

    for u_id in user_ids:
        try:
            await bot.send_message(chat_id=u_id, text=ad_text)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await message.answer(f"✅ Reklama yakunlandi. {success} ta odamga muvaffaqiyatli yetib bordi.")


# --- RENDER PORT XATOSINI OLDINI OLISH UCHUN SOXTA SERVER ---
def run_dummy_server():
    class DummyHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"Bot muvaffaqiyatli ishlamoqda!")

    port = int(os.environ.get("PORT", 10000))
    with socketserver.TCPServer(("", port), DummyHandler) as httpd:
        print(f"Render uchun soxta server {port}-portda ishga tushdi.")
        httpd.serve_forever()


# --- BOTNI ISHGA TUSHIRISH ---
async def main():
    init_db()
    print("🚀 Bot muvaffaqiyatli ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    threading.Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(main())
