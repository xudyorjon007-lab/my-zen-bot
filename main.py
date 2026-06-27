import asyncio
import logging
import sqlite3
import time
import os
import threading
from datetime import datetime
from flask import Flask
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# 1. BOT SOZLAMALARI
TOKEN = "8931216163:AAH2n19Jlcflxa7YCix_sdEAcCIF4GrmU38"  # Bot tokeni
ADMIN_ID = 7578712290  # Telegram ID'ingiz
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# SOXTA FLASK SERVER (Render "no open ports" xatoligini bermasligi va o'chib qolmasligi uchun)
flask_app = Flask(__name__)


@flask_app.route('/')
def home():
    return "Bot is active and running 24/7!"


def run_flask():
    # Render avtomatik taqdim etadigan PORT o'zgaruvchisini oladi, bo'lmasa 10000 da ishlaydi
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)


# 2. MA'LUMOTLAR BAZASI TIZIMI
def init_db():
    conn = sqlite3.connect("quiz_bot.db")
    cursor = conn.cursor()

    # Foydalanuvchilar jadvali
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            total_score INTEGER DEFAULT 0
        )
    """)

    # AGAR ESKI BAZA BO'LSA: last_passed_date ustuni yo'qligi sababli xato bermasligi uchun avtomatik qo'shish
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN last_passed_date TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        # Ustun allaqachon mavjud bo'lsa xatoni e'tiborsiz qoldiradi
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            opt1 TEXT, opt2 TEXT, opt3 TEXT, opt4 TEXT,
            correct_index INTEGER,
            explanation TEXT
        )
    """)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM questions")
    if cursor.fetchone()[0] == 0:
        default_questions = [
            ("IP manzillar nechanchi qatlamda ishlaydi?", "Layer 1", "Layer 2", "Layer 3", "Layer 4", 2,
             "IP manzillar OSI modelining Tarmoq (Network) qatlamida ishlaydi."),
            ("Python dasturlash tilida konstanta qiymatni qaysi ma'lumot turi saqlaydi (o'zgarmas)?", "List", "Tuple",
             "Dictionary", "Set", 1, "Tuple - o'zgarmas (immutable) ro'yxat hisoblanadi."),
            ("Kiberxavfsizlikda 'CIA' uchligining ma'nosi nima?", "Central Intelligence Agency",
             "Confidentiality, Integrity, Availability", "Control, Inspect, Access", "Crypto, Internal, Authenticate",
             1, "CIA - Maxfiylik, Butunlik va Foydalanish osonligi demakdir."),
            ("Quyidagilardan qaysi biri veb-saytlarning ma'lumotlar bazasiga hujum turi hisoblanadi?", "XSS", "DDoS",
             "SQL Injection", "Phishing", 2,
             "SQL Injection orqali buzg'unchilar bazaga zararli so'rovlar yuborishi mumkin."),
            ("Kompyuter o'chirilganda undagi ma'lumotlar o'chib ketadigan xotira qaysi?", "HDD", "SSD", "ROM", "RAM", 3,
             "RAM - tezkor xotira bo'lib, energiya o'chganda ma'lumotlarni yo'qotadi."),
            ("Dasturlashda HTTP 404 xatoligi nimani anglatadi?", "Server topilmadi", "Sahifa topilmadi",
             "Ruxsat berilmagan", "Ichki server xatosi", 1,
             "404 Not Found - so'ralgan sahifa serverda mavjud emasligini bildiradi."),
            ("Linux operatsion tizimining asosi (yuragi) nima deyiladi?", "Shell", "Kernel", "Terminal", "Root", 1,
             "Kernel (Yadro) operatsion tizimning eng asosiy qismi hisoblanadi."),
            ("Git tizimida o'zgarishlarni masofaviy serverga (GitHub) yuborish buyrug'i qaysi?", "git pull",
             "git commit", "git push", "git clone", 2, "git push maxalliy o'zgarishlarni serverga yuklaydi."),
            ("Tarmoq xavfsizligini ta'minlovchi va chiquvchi/kiruvchi trafikni filtrlovchi tizim?", "Router", "Switch",
             "Firewall", "Hub", 2, "Firewall (Tarmoq ekrani) ruxsat etilmagan ulanishlarni to'sadi."),
            ("Python'da funksiya yaratish uchun qaysi kalit so'zdan foydalaniladi?", "func", "function", "def",
             "define", 2, "Python'da funksiyalar 'def' kalit so'zi orqali boshlanadi."),
            ("Dunyodagi birinchi dasturchi kim deb tan olingan?", "Alan Turing", "Ada Lovelace", "Bill Gates",
             "Steve Jobs", 1, "Ada Lovelace dunyodagi birinchi ayol dasturchi hisoblanadi."),
            ("Veb-sahifalarning vizual ko'rinishi va dizaynini yaratishda nima ishlatiladi?", "HTML", "CSS",
             "JavaScript", "PHP", 1, "CSS sahifalarga rang, dizayn va uslub berish uchun qo'llaniladi."),
            ("Ping buyrug'i qaysi protokol asosida ishlaydi?", "TCP", "UDP", "ICMP", "HTTP", 2,
             "Ping tarmoq aloqasini tekshirish uchun ICMP protokolidan foydalanadi."),
            ("Ma'lumotlar bazasida jadvaldan ma'lumotlarni o'chirish buyrug'i qaysi?", "REMOVE", "CLEAR", "DROP",
             "DELETE", 3, "DELETE buyrug'i jadval ichidagi qatorlarni o'chirish uchun ishlatiladi."),
            ("Asinxron dasturlashni qo'llovchi Python kutubxonasi qaysi?", "Requests", "Time", "Asyncio", "Math", 2,
             "Asyncio - Python'da asinxron kod yozish uchun kutubxonadir."),
            ("Shifrlash kaliti bitta bo'lgan kriptografiya qanday nomlanadi?", "Asimmetrik", "Simmetrik",
             "Ochiq kalitli", "Gibrid", 1,
             "Simmetrik shifrlashda ma'lumotni shifrlash va ochish uchun bir xil kalit qo'llaniladi."),
            ("Wi-Fi tarmoqlarida eng xavfsiz shifrlash standarti qaysi?", "WEP", "WPA", "WPA2", "WPA3", 3,
             "WPA3 hozirgi kunda Wi-Fi xavfsizligi uchun eng mukammal standart hisoblanadi."),
            ("Dasturlashda API so'zining kengaytmasi nima?", "Application Programming Interface",
             "Advanced Program Integration", "Automated Protocol Internet", "Array Processing Information", 0,
             "API - dasturlarning o'zaro ma'lumot almashish interfeysidir."),
            ("Docker loyihalarni qanday muhitda ishga tushiradi?", "Virtual Mashina", "Konteyner (Container)",
             "Bulutli server", "Lokal disk", 1,
             "Docker ilovalarni izolyatsiyalangan konteynerlarda ishlatishga imkon beradi."),
            ("Quyidagilardan qaysi biri qidiruv tizimi emas?", "Google", "Bing", "DuckDuckGo", "Ubuntu", 3,
             "Ubuntu - bu Linux'ga asoslangan operatsion tizim."),
            ("Tarmoq tezligi asosan qaysi birlikda o'lchanadi?", "Bayt", "Gers", "Bit/sekund (Mbps)", "Metr/sekund", 2,
             "Tarmoq tezligi sekundiga bitlar (Mbps) bilan o'lchanadi."),
            ("Python'da xatoliklarni ushlab qolish va boshqarish bloki qaysi?", "if / else", "try / except",
             "for / while", "do / untill", 1, "try/except bloki kutilmagan xatolarni ushlab qoladi."),
            ("Localhost manzili IP ko'rinishida qanday yoziladi?", "192.168.1.1", "127.0.0.1", "10.0.0.1", "8.8.8.8", 1,
             "127.0.0.1 - kompyuterning o'ziga murojaat qilish IP manzilidir."),
            ("Saytlarda xavfsiz va shifrlangan ulanish sertifikati nima deyiladi?", "SSL/TLS", "DNS", "FTP", "SSH", 0,
             "SSL sertifikati HTTPS brauzer aloqasini shifrlaydi."),
            ("GitHub tizimida loyihani nusxalab olish (skachat qilish) buyrug'i?", "git push", "git init", "git clone",
             "git status", 2, "git clone masofaviy repozitoriyni nusxalab beradi.")
        ]
        cursor.executemany("""
            INSERT INTO questions (question, opt1, opt2, opt3, opt4, correct_index, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, default_questions)
        conn.commit()
    conn.close()


def add_user(user_id, username, full_name):
    conn = sqlite3.connect("quiz_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
                   (user_id, username, full_name))
    conn.commit()
    conn.close()


def check_user_passed_today(user_id):
    conn = sqlite3.connect("quiz_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT last_passed_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    today = datetime.now().strftime("%Y-%m-%d")
    if row and row[0] == today:
        return True
    return False


def update_user_date(user_id, score):
    conn = sqlite3.connect("quiz_bot.db")
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("UPDATE users SET total_score = total_score + ?, last_passed_date = ? WHERE user_id = ?",
                   (score, today, user_id))
    conn.commit()
    conn.close()


def get_random_quiz():
    conn = sqlite3.connect("quiz_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT question, opt1, opt2, opt3, opt4, correct_index, explanation FROM questions ORDER BY RANDOM() LIMIT 25")
    rows = cursor.fetchall()
    conn.close()

    quiz_list = []
    for row in rows:
        quiz_list.append({
            "question": row[0],
            "options": [row[1], row[2], row[3], row[4]],
            "correct_index": row[5],
            "explanation": row[6]
        })
    return quiz_list


# 3. FSM STATES
class QuizState(StatesGroup):
    answering = State()


# 4. KEYBOARDS
def main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Bugungi Testni Boshlash", callback_data="start_quiz")
    builder.adjust(1)
    return builder.as_markup()


def quiz_options_keyboard(options, question_idx):
    builder = InlineKeyboardBuilder()
    for idx, option in enumerate(options):
        builder.button(text=option, callback_data=f"ans_{question_idx}_{idx}")
    builder.adjust(1)
    return builder.as_markup()


def resume_quiz_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="➡️ Testni Davom Ettirish", callback_data="resume_quiz")
    return builder.as_markup()


# 5. HANDLERS
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()

    if current_state == QuizState.answering.state:
        await message.answer(
            "⚠️ **Siz hozir test jarayonidasiz!**\n\n"
            "Pastdagi tugmani bosing va testni qolgan joyidan davom ettiring!",
            reply_markup=resume_quiz_keyboard(),
            parse_mode="Markdown"
        )
        return

    if check_user_passed_today(user_id):
        await message.answer(
            "❌ **Siz bugungi test varianti bo'yicha urinishingizdan foydalandingiz!**\n\n"
            "Har kuni faqat 1 marta test topshirish mumkin. **Yangi test ertaga ochiladi!**"
        )
        return

    add_user(user_id, message.from_user.username, message.from_user.full_name)

    welcome_text = (
        f"👋 Salom, {message.from_user.full_name}!\n\n"
        f"🤖 Bugungi mutlaqo yangi **25 talik test variantingiz** tayyor!\n"
        f"⏱ **Vaqt:** 10 daqiqa.\n"
        f"⚠️ **Qoida:** Bugun testni faqat bir marta boshlay olasiz, qayta urinish ertaga ochiladi."
    )
    await message.answer(welcome_text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")


@dp.callback_query(F.data == "resume_quiz")
async def cb_resume_quiz(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await send_next_question(callback.message, state, is_resume=True)


@dp.callback_query(F.data == "start_quiz")
async def cb_start_quiz(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    if check_user_passed_today(user_id):
        await callback.answer("Bugun test topshirib bo'lgansiz!", show_alert=True)
        await callback.message.edit_text("❌ Bugungi urinish tugagan. Ertaga yangi variant ochiladi.")
        return

    await callback.answer()
    user_quiz_data = get_random_quiz()
    start_time = time.time()

    await state.set_state(QuizState.answering)
    await state.update_data(
        current_question=0,
        score=0,
        history=[],
        quiz_data=user_quiz_data,
        start_time=start_time
    )
    await send_next_question(callback.message, state)


async def send_next_question(message: types.Message, state: FSMContext, is_resume=False):
    data = await state.get_data()

    elapsed_time = time.time() - data["start_time"]
    if elapsed_time > 600:
        warning_text = "⏱ **Afsus, 10 daqiqalik vaqtingiz tugadi!** Natijalar qayd etilmoqda..."
        if is_resume:
            await message.answer(warning_text)
        else:
            await message.edit_text(warning_text)
        await finish_quiz(message, state, timeout=True)
        return

    q_idx = data["current_question"]
    quiz_data = data["quiz_data"]

    if q_idx >= len(quiz_data):
        await finish_quiz(message, state)
        return

    remaining_min = int((600 - elapsed_time) // 60)
    remaining_sec = int((600 - elapsed_time) % 60)

    question_item = quiz_data[q_idx]
    text = (
        f"📝 **Savol {q_idx + 1} / {len(quiz_data)}**\n"
        f"⏱ **Qolgan vaqt:** {remaining_min:02d}:{remaining_sec:02d}\n\n"
        f"{question_item['question']}"
    )

    kb = quiz_options_keyboard(question_item["options"], q_idx)

    if is_resume:
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(QuizState.answering, F.data.startswith("ans_"))
async def handle_answer(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()

    if time.time() - data["start_time"] > 600:
        await callback.message.edit_text("⏱ **Vaqt tugab qoldi!**")
        await finish_quiz(callback.message, state, timeout=True)
        return

    parts = callback.data.split("_")
    q_idx = int(parts[1])
    chosen_idx = int(parts[2])

    if q_idx != data["current_question"]:
        return

    quiz_data = data["quiz_data"]
    question_item = quiz_data[q_idx]
    correct = question_item["correct_index"]

    score_increment = 0
    result_emoji = "❌"

    if chosen_idx == correct:
        score_increment = 4
        result_emoji = "✅"

    new_score = data["score"] + score_increment
    history = data["history"]
    history.append({"q_num": q_idx + 1, "res": result_emoji})

    await state.update_data(current_question=q_idx + 1, score=new_score, history=history)

    feedback_text = (
        f"{result_emoji} **Sizning javobingiz:** {question_item['options'][chosen_idx]}\n"
        f"ℹ️ **Izoh:** {question_item['explanation']}\n\n"
        f"Joriy ball: {new_score}"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="➡️ Keyingi Savol", callback_data="next_question")
    await callback.message.edit_text(feedback_text, reply_markup=builder.as_markup(), parse_mode="Markdown")


@dp.callback_query(QuizState.answering, F.data == "next_question")
async def cb_next_question(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await send_next_question(callback.message, state)


async def finish_quiz(message: types.Message, state: FSMContext, timeout=False):
    data = await state.get_data()
    final_score = data["score"]
    user_id = message.chat.id

    update_user_date(user_id, final_score)

    user_username = message.chat.username
    user_fullname = message.chat.full_name or "Yashirin foydalanuvchi"
    user_link = f"https://t.me/{user_username}" if user_username else "Mavjud emas"
    user_mention = f"@{user_username}" if user_username else "Nik qo'yilmagan"

    total_time_spent = int(time.time() - data["start_time"])
    spent_min = total_time_spent // 60
    spent_sec = total_time_spent % 60

    status_msg = "⏱ **Vaqt tugadi!**\n" if timeout else "🎉 **Test Yakunlandi!**\n"
    report = (
        f"{status_msg}\n"
        f"💰 To'plagan balingiz: **{final_score} ball / 100**\n"
        f"⏳ Sarflangan vaqt: **{spent_min} daqiqa, {spent_sec} soniya**\n\n"
        f"📊 Bugungi urinishingiz yakunlandi. Yangi test ertaga ochiladi!"
    )

    try:
        await message.edit_text(report, parse_mode="Markdown")
    except Exception:
        await message.answer(report, parse_mode="Markdown")

    admin_alert = (
        f"🔔 **Kunlik test natijasi keldi!** {'(Taymer tugadi ⏱)' if timeout else ''}\n\n"
        f"👤 **Foydalanuvchi:** {user_fullname}\n"
        f"💬 **Username:** {user_mention}\n"
        f"🔗 **Profil linki:** {user_link}\n"
        f"⏳ Sarflangan vaqt: {spent_min}m {spent_sec}s\n\n"
        f"🎯 **To'plagan bali:** `{final_score} ball / 100`"
    )

    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_alert, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        logging.error(f"Admin bildirishnomasida xato: {e}")

    await state.clear()


async def main():
    init_db()

    # Render'da "no open ports" xatoligi chiqmasligi uchun Flask portini parallel oqimda ochamiz
    threading.Thread(target=run_flask, daemon=True).start()

    print("🤖 Har kuni yangilanadigan 100% himoyali Quiz Bot ishga tushdi...")

    # Conflict xatosini oldini olish uchun avvalgi kesh so'rovlarini tozalab pollingni boshlaymiz
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
