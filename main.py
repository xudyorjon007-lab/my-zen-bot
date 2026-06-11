import os
import time
import psutil
import requests
import logging
import hashlib

# --- LOG TIZIMI ---
logging.basicConfig(
    filename="cyber_guard_security.log",
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s")

# --- XAVFSIZLIK SOZLAMALARI ---
TOKEN = "8933798485:AAEMnMrd_2oXKUsKNuKBu9Zk2N3zCYgNbzM"  # Bu yerga Bot tokeningizni yozing
CHAT_ID = "7578712290"  # Bu yerga Telegram ID'ngizni yozing

# 1. Ma'lum bo'lgan zararli dasturlar nomlari (Blacklist)
CRITICAL_BLACK_LIST = [
    "miner.exe", "ransomware.exe", "trojan.exe", "keylogger.exe",
    "mimikatz.exe", "nc.exe", "netcat.exe", "virus.bat"
]

# 2. Mashhur viruslarning MD5 xesh (hash) imzolari bazasi
KNOWN_VIRUS_HASHES = [
    "44d88612fea8a8f36de82e1278abb02f",  # EICAR Xalqaro test virusi xeshi
    "5e8841671c6ecb5803974c5284178dd2",  # Namuna uchun troyan xeshi
    "8bccf2791696238380fb600df8b7ec6f"  # Namuna uchun miner xeshi
]

# 3. Yashirincha ishga tushsa xavfli bo'lgan tizim instrumentlari
SUSPICIOUS_TOOLS = ["powershell.exe", "cmd.exe", "wscript.exe", "cscript.exe"]

# 4. Viruslar eng ko'p yashirinadigan xavfli jildlar yo'llari
DANGEROUS_PATHS = ["\\appdata\\local\\temp", "\\appdata\\roaming", "\\users\\public"]


def get_file_hash(file_path):
    """Faylning ichki MD5 xesh kodini hisoblash funksiyasi"""
    hash_md5 = hashlib.md5()
    try:
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
    except Exception as e:
        logging.error(f"Xesh hisoblashda xatolik ({file_path}): {e}")
    return None


def send_critical_alert(proc_name, pid, path, reason, file_hash=None):
    """Telegramga jiddiy kiber-xavfsizlik xabarini yuborish"""
    f_hash = file_hash if file_hash else "Aniqlanmadi"
    text = (
        f"🚨 <b>[CYBER GUARD: CRITICAL INCIDENT]</b> 🚨\n\n"
        f"⚠️ <b>Xavf turi:</b> Zararli dastur bloklandi\n"
        f"🔥 <b>Dastur nomi:</b> <code>{proc_name}</code> (PID: {pid})\n"
        f"🛡️ <b>Asos:</b> {reason}\n"
        f"🔑 <b>MD5 Hash:</b> <code>{f_hash}</code>\n"
        f"📍 <b>Manba yo'li:</b> <code>{path}</code>\n\n"
        f"✅ <b>Holat:</b> Jarayon xotiradan o'chirildi, tizim barqaror."
    )
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except Exception as e:
        logging.error(f"Telegram ogohlantirishida xatolik: {e}")


def enforce_security():
    logging.info("Cyber Guard xavfsizlik yadrosi muvaffaqiyatli ishga tushdi.")
    print("🛡️ [Cyber Guard Core] Tizim jiddiy himoya rejimida ishlamoqda...")
    print("🔬 MD5 Xesh imzolari bo'yicha tekshirish moduli faol.")
    print("--------------------------------------------------")

    while True:
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                proc_name = proc.info['name'].lower()
                proc_pid = proc.info['pid']
                proc_exe = proc.info['exe']

                if not proc_exe:
                    continue

                proc_exe_lower = proc_exe.lower()
                triggered = False
                reason = ""
                current_hash = None

                # ---- 1-BOSQICH: XESH (HASH) IMZOSI BO'YICHA TEKSHIRISH ----
                current_hash = get_file_hash(proc_exe)
                if current_hash in KNOWN_VIRUS_HASHES:
                    triggered = True
                    reason = "Faylning raqamli barmoq izi (MD5 Hash) viruslar bazasiga tushdi!"

                # ---- 2-BOSQICH: NOM (BLACKLIST) BO'YICHA TEKSHIRISH ----
                elif proc_name in CRITICAL_BLACK_LIST:
                    triggered = True
                    reason = "Ma'lum bo'lgan zararli dasturlar ro'yxatiga (Blacklist) tushdi."

                # ---- 3-BOSQICH: FONDAGI SHUBHALI SCRIPTlarni TEKSHIRISH ----
                elif proc_name in SUSPICIOUS_TOOLS:
                    parent = psutil.Process(proc_pid).parent()
                    if parent and parent.name().lower() not in ["explorer.exe", "pycharm64.exe", "python.exe"]:
                        triggered = True
                        reason = f"Shubhali fondagi skript faolligi (Parent Process: {parent.name()})."

                # ---- 4-BOSQICH: XAVFLI JILDLARDAN ISHGA TUSHISHNI TEKSHIRISH ----
                else:
                    for dangerous_path in DANGEROUS_PATHS:
                        if dangerous_path in proc_exe_lower:
                            if proc_name.endswith(".exe") and "python" not in proc_name:
                                triggered = True
                                reason = f"Dastur xavfli va yashirin jilddan o'zboshimchalik bilan ishga tushdi ({dangerous_path})."
                                break

                # ---- AGAR XAVF ANIQLANSA (DARHOL ACTION) ----
                if triggered:
                    # 1. Darhol jarayonni tugatish (Xotiradan o'chirish)
                    p = psutil.Process(proc_pid)
                    p.kill()
                    logging.warning(f"Zararli jarayon to'xtatildi: {proc_name} (PID: {proc_pid})")

                    # 2. Manba faylini diskdan xavfsiz o'chirish (Xatoliklarni aylanib o'tish)
                    time.sleep(0.2)
                    try:
                        if os.path.exists(proc_exe):
                            os.remove(proc_exe)
                            logging.info(f"Zararli fayl diskdan o'chirildi: {proc_exe}")
                    except PermissionError:
                        # Tizim fayllarida PermissionError bersa, dastur endi sinib qolmaydi!
                        logging.warning(f"Tizim fayli bo'lgani uchun o'chirishga ruxsat bo'lmadi: {proc_exe}")
                    except Exception as e:
                        logging.error(f"Faylni o'chirishda xatolik: {e}")

                    # 3. Telegramga alert yuborish
                    send_critical_alert(proc_name, proc_pid, proc_exe, reason, current_hash)

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        time.sleep(0.5)


if __name__ == "__main__":
    try:
        enforce_security()
    except KeyboardInterrupt:
        logging.info("Tizim foydalanuvchi tomonidan to'xtatildi.")
        print("\n🛡️ Himoya vaqtincha faolsizlantir")