import logging
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F

# === SOZLAMALAR ===
BOT_TOKEN = '8606542982:AAEJI8S8CN5IDkqet1XCEZDZkPIPfIIHm3c'
VIRUSTOTAL_API_KEY = 'f623c4e2644323d4b417515a7f54a5b7c353182147d6c141aa93782ae167221a'  # Saytdan olingan API kalit

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ==========================================
# VIRUSTOTAL BILAN ISHLASH FUNKSIYASI
# ==========================================
async def scan_file_via_virustotal(file_path: str):
    """Faylni VirusTotal API orqali haqiqiy tekshiruvdan o'tkazadi"""
    url = "https://www.virustotal.com/api/v3/files"
    headers = {
        "x-apikey": VIRUSTOTAL_API_KEY
    }

    async with aiohttp.ClientSession() as session:
        # 1. Faylni VirusTotal serveriga yuklash
        with open(file_path, 'rb') as f:
            data = {'file': f}
            async with session.post(url, headers=headers, data=data) as response:
                if response.status != 200:
                    return None, f"Xatolik yuz berdi. Status kod: {response.status}"

                result = await response.json()
                analysis_id = result['data']['id']

        # 2. Tekshiruv natijasini kutish (VirusTotal tahlil qilishi uchun 10 soniya kutamiz)
        analysis_url = f"https://www.virustotal.com/api/v3/analyses/{analysis_id}"
        await asyncio.sleep(10)

        async with session.get(analysis_url, headers=headers) as check_response:
            if check_response.status == 200:
                res_data = await check_response.json()
                stats = res_data['data']['attributes']['stats']

                # Natijalarni ajratib olish
                malicious = stats.get('malicious', 0)
                suspicious = stats.get('suspicious', 0)
                harmless = stats.get('harmless', 0)
                undetected = stats.get('undetected', 0)

                return {
                    "malicious": malicious,
                    "suspicious": suspicious,
                    "harmless": harmless,
                    "undetected": undetected
                }, "OK"

    return None, "Natijani olishda xatolik."


# ==========================================
# FAYLLARI QABUL QILISH VA TEKSHIRISH
# ==========================================
@dp.message(F.document | F.audio | F.video | F.photo)
async def handle_suspicious_file(message: types.Message):
    # Foydalanuvchiga jarayon boshlanganini bildiramiz
    status_msg = await message.reply(
        "📥 **Fayl qabul qilindi!**\n"
        "⏳ Hozir faylni xavfsiz serverga yuklab, **VirusTotal (70+ Antivirus)** orqali tekshirishni boshlayapman. Iltimos kuting..."
    )

    # Botga kelgan fayl ID-sini olish
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_name = "photo.jpg"
    else:
        await status_msg.edit_text("❌ Faqat hujjat yoki media fayllarni tekshira olaman.")
        return

    try:
        # Telegram serveridan faylni bot xotirasiga yuklab olish
        file_info = await bot.get_file(file_id)
        download_path = f"downloads_{file_name}"
        await bot.download_file(file_info.file_path, download_path)

        await status_msg.edit_text(
            "🔬 **Fayl muvaffaqiyatli yuklandi.**\nVirusTotal bulutli skanerida tahlil qilinmoqda...")

        # VirusTotal-ga yuborish
        stats, status = await scan_file_via_virustotal(download_path)

        # Vaqtinchalik yuklangan faylni o'chirish (xavfsizlik va xotira uchun)
        import os
        if os.path.exists(download_path):
            os.remove(download_path)

        if stats:
            # Natijalarni hisoblash va chiroyli matn tayyorlash
            total_antiviruses = stats['malicious'] + stats['suspicious'] + stats['harmless'] + stats['undetected']

            if stats['malicious'] > 0:
                result_text = (
                    f"🚨 🛑 **DIQQAT! XAVFLI FAYL ANIQLANDI!** 🛑 🚨\n\n"
                    f"📁 Fayl nomi: `{file_name}`\n"
                    f"📊 **Antiviruslar xulosasi:**\n"
                    f"❌ Zararli (Malicious): **{stats['malicious']}** ta antivirus\n"
                    f"⚠️ Shubhali (Suspicious): **{stats['suspicious']}** ta antivirus\n"
                    f"✅ Toza (Harmless): {stats['harmless']} ta\n\n"
                    f"🔴 **Xulosa:** {total_antiviruses} ta antivirusdan **{stats['malicious']} tasi** bu faylni VIRUS deb topdi! **BU FAYLNI ASLO OCHMANG!**"
                )
            else:
                result_text = (
                    f"✅ **Skanerlash yakunlandi. Fayl xavfsiz!**\n\n"
                    f"📁 Fayl nomi: `{file_name}`\n"
                    f"🟢 Antiviruslar xulosasi: 0 ta zararli kod topildi.\n"
                    f"🛡️ Jami {total_antiviruses} ta xalqaro antivirus tizimi faylni **TOZA** deb tasdiqladi."
                )

            await status_msg.edit_text(result_text, parse_mode="Markdown")
        else:
            await status_msg.edit_text(f"❌ Tekshiruvda xatolik: {status}")

    except Exception as e:
        logging.error(f"Skanerlashda xato: {e}")
        await status_msg.edit_text("❌ Faylni yuklash yoki tekshirish jarayonida texnik xatolik yuz berdi.")


@dp.message()
async def echo_start(message: types.Message):
    await message.answer(
        "👋 Shubhali faylni (masalan, `.apk` yoki `.exe`) menga yuboring, uni haqiqiy antiviruslar orqali tekshirib beraman!")


# ==========================================
# BOTNI ISHGA TUSHIRISH
# ==========================================
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())