# -*- coding: utf-8 -*-
"""
بوت استضافة بايثون - النسخة الآمنة للاستضافة
تم التعديل: @llllllIlIlIlIlIlIlIl
"""

import telebot
import subprocess
import os
import shutil
from telebot import types
import time
from datetime import datetime
import psutil
import sqlite3
import logging
import sys
import atexit
import requests
import re
from pathlib import Path
import hashlib
import signal
from dotenv import load_dotenv

# تحميل متغيرات البيئة من ملف .env
load_dotenv()

# --- Flask Keep Alive ---
from flask import Flask, send_file, jsonify
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <html>
    <head><title>بوت استضافة بايثون</title></head>
    <body style="font-family: Arial; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 50px;">
        <h1>بوت استضافة بايثون - نسخة الأدمن</h1>
        <h2>🐍 استضافة وتشغيل ملفات بايثون</h2>
        <p>🔐 للأدمن فقط</p>
        <p>🚀 تشغيل تلقائي للملفات</p>
        <p>🛡️ حماية متقدمة</p>
    </body>
    </html>
    """

@app.route('/file/<file_hash>')
def serve_file(file_hash):
    """تقديم الملفات المستضافة"""
    try:
        for user_id in user_files:
            for file_name in user_files[user_id]:
                expected_hash = hashlib.md5(f"{user_id}_{file_name}".encode()).hexdigest()
                if expected_hash == file_hash:
                    script_folder = get_script_folder(user_id, file_name)
                    file_path = os.path.join(script_folder, file_name)
                    if os.path.exists(file_path):
                        return send_file(file_path, as_attachment=False)
        return "الملف غير موجود", 404
    except Exception as e:
        logger.error(f"خطأ في تقديم الملف {file_hash}: {e}")
        return "خطأ في تقديم الملف", 500

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

def run_flask():
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    print("🌐 سيرفر Flask بدأ العمل")

# --- الإعدادات الآمنة ---
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    print("❌ خطأ: لم يتم تعيين TELEGRAM_BOT_TOKEN في متغيرات البيئة")
    print("📝 قم بإنشاء ملف .env وأضف التوكن كما في التعليمات")
    sys.exit(1)

OWNER_ID = os.getenv('OWNER_ID')
if not OWNER_ID:
    print("❌ خطأ: لم يتم تعيين OWNER_ID في متغيرات البيئة")
    sys.exit(1)

ADMIN_ID = os.getenv('ADMIN_ID', OWNER_ID)

try:
    OWNER_ID = int(OWNER_ID)
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    print("❌ خطأ: معرفات المستخدمين يجب أن تكون أرقام")
    sys.exit(1)

# إعداد المجلدات
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')
LOGS_DIR = os.path.join(BASE_DIR, 'execution_logs')

# إنشاء المجلدات الضرورية
for directory in [UPLOAD_BOTS_DIR, IROTECH_DIR, LOGS_DIR]:
    os.makedirs(directory, exist_ok=True)

# تهيئة البوت
bot = telebot.TeleBot(TOKEN)

# --- قيود النظام ---
MAX_CONCURRENT_SCRIPTS = 5
MAX_SCRIPT_RUNTIME = 300  # 5 دقائق
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 ميجابايت
MAX_TOTAL_SCRIPTS_PER_USER = 10

# قائمة المكاتب المحظورة
BANNED_PACKAGES = {
    'os', 'sys', 'subprocess', 'shutil', 'psutil', 'signal',
    'ctypes', 'socket', 'multiprocessing', 'threading'
}

# --- هياكل البيانات ---
bot_scripts = {}
user_files = {}
admin_ids = {ADMIN_ID, OWNER_ID}

PROTECTED_PACKAGES = {
    'pip', 'setuptools', 'wheel',
    'pytelegrambotapi', 'telebot',
    'flask', 'requests', 'psutil', 'sqlite3'
}

# --- إعداد السجلات ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, 'bot.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- أزرار الأوامر ---
ADMIN_BUTTONS = [
    ["📤 رفع ملف", "📂 ملفاتي"],
    ["⚡ سرعة البوت", "📊 الإحصائيات"],
    ["🟢 الملفات النشطة", "📚 المكاتب"],
    ["📞 تواصل"]
]

# --- دوال قاعدة البيانات ---
def init_db():
    """تهيئة قاعدة البيانات"""
    logger.info(f"تهيئة قاعدة البيانات في: {DATABASE_PATH}")
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS user_files
                     (user_id INTEGER, file_name TEXT,
                      PRIMARY KEY (user_id, file_name))''')
        c.execute('''CREATE TABLE IF NOT EXISTS admins
                     (user_id INTEGER PRIMARY KEY)''')
        
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
        if ADMIN_ID != OWNER_ID:
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (ADMIN_ID,))
        
        conn.commit()
        conn.close()
        logger.info("تم تهيئة قاعدة البيانات بنجاح")
    except Exception as e:
        logger.error(f"خطأ في تهيئة قاعدة البيانات: {e}")

def load_data():
    """تحميل البيانات من قاعدة البيانات"""
    logger.info("جاري تحميل البيانات...")
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        
        c.execute('SELECT user_id, file_name FROM user_files')
        for user_id, file_name in c.fetchall():
            if user_id not in user_files:
                user_files[user_id] = []
            user_files[user_id].append(file_name)
        
        c.execute('SELECT user_id FROM admins')
        admin_ids.update(user_id for (user_id,) in c.fetchall())
        
        conn.close()
        logger.info(f"تم تحميل البيانات: {len(user_files)} سجل ملف")
    except Exception as e:
        logger.error(f"خطأ في تحميل البيانات: {e}")

# --- دوال مساعدة ---
def get_user_folder(user_id):
    """الحصول على مجلد المستخدم أو إنشاؤه"""
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def get_script_folder(user_id, file_name):
    """الحصول على المجلد المخصص للسكربت أو إنشاؤه"""
    user_folder = get_user_folder(user_id)
    script_name_no_ext = os.path.splitext(file_name)[0]
    script_folder = os.path.join(user_folder, script_name_no_ext)
    os.makedirs(script_folder, exist_ok=True)
    return script_folder

# *** دالة جديدة لتنظيف السجلات القديمة ***
def cleanup_old_logs():
    """حذف ملفات السجل القديمة لتوفير المساحة"""
    logger.info("🧹 جاري فحص السجلات القديمة للتنظيف...")
    current_time = time.time()
    max_age = 24 * 60 * 60  # 24 ساعة
    
    deleted_count = 0
    try:
        if not os.path.exists(LOGS_DIR):
            return

        for filename in os.listdir(LOGS_DIR):
            file_path = os.path.join(LOGS_DIR, filename)
            
            # لا نحذف سجل البوت الرئيسي
            if filename == 'bot.log':
                continue
                
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                
                # إذا كان الملف قديماً جداً (أكثر من 24 ساعة)
                if file_age > max_age:
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"تعذر حذف السجل القديم {filename}: {e}")
        
        if deleted_count > 0:
            logger.info(f"✅ تم تنظيف {deleted_count} ملف سجل قديم.")
        else:
            logger.info("✅ السجلات نظيفة، لم يتم حذف شيء.")
            
    except Exception as e:
        logger.error(f"خطأ أثناء تنظيف السجلات: {e}")

def is_bot_running(script_owner_id, file_name):
    """التحقق من تشغيل السكربت (دون حذف السجل)"""
    script_key = f"{script_owner_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    
    if not script_info or not script_info.get('process'):
        return False
        
    try:
        proc = psutil.Process(script_info['process'].pid)
        is_running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        
        if not is_running:
            script_info['process'] = None
        
        return is_running
    except psutil.NoSuchProcess:
        script_info['process'] = None
        return False
    except Exception:
        script_info['process'] = None
        return False

def safe_send_message(chat_id, text, parse_mode=None, reply_markup=None):
    try:
        return bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception as e:
        if "can't parse entities" in str(e):
            return bot.send_message(chat_id, text, reply_markup=reply_markup)
        else:
            raise e

def safe_reply_to(message, text, parse_mode=None, reply_markup=None):
    try:
        return bot.reply_to(message, text, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception as e:
        if "can't parse entities" in str(e):
            return bot.reply_to(message, text, reply_markup=reply_markup)
        else:
            raise e

def safe_edit_message(chat_id, message_id, text, parse_mode=None, reply_markup=None):
    try:
        return bot.edit_message_text(text, chat_id, message_id, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception as e:
        if "can't parse entities" in str(e):
            return bot.edit_message_text(text, chat_id, message_id, reply_markup=reply_markup)
        else:
            raise e

# --- فحص الكود الخبيث ---
def check_malicious_code(file_path):
    critical_patterns = [
        'sudo ', 'su ', 'rm -rf', 'fdisk', 'mkfs', 'dd if=',
        'shutdown', 'reboot', 'halt',
        '/ls', '/cd', '/pwd', '/cat', '/grep', '/find',
        '/del', '/get', '/getall', '/download', '/upload',
        '/steal', '/hack', '/dump', '/extract', '/copy',
        'bot.send_document', 'send_document', 'bot.get_file',
        'download_file', 'send_media_group',
        'os.system("rm', 'os.system("sudo', 'os.system("format',
        'subprocess.call(["rm"', 'subprocess.call(["sudo"',
        'subprocess.run(["rm"', 'subprocess.run(["sudo"',
        'os.system("/bin/', 'os.system("/usr/', 'os.system("/sbin/',
        'shutil.rmtree("/"', 'os.remove("/"', 'os.unlink("/"',
        'requests.post.*files=', 'urllib.request.urlopen.*data=',
        'os.kill(', 'signal.SIGKILL', 'psutil.process_iter',
        'os.environ["PATH"]', 'os.putenv("PATH"',
        'setuid', 'setgid', 'chmod 777', 'chown root',
        'os.system("format', 'subprocess.call(["format"', 'subprocess.run(["format"',
        '__import__', 'eval(', 'exec(', 'compile(',
        'getattr', 'setattr', 'delattr',
        'open("/etc/', 'open("/proc/', 'open("/dev/',
        '.read()', '.write()', '.close()',
        'pickle.load', 'marshal.load',
        'yaml.load', 'json.loads',
        'socket.socket', '.bind(', '.connect(',
        'urllib.request', 'ftplib', 'smtplib',
        'telnetlib', 'poplib', 'imaplib',
        'sqlite3.connect(":memory:")',
        'tempfile.', 'mkstemp', 'mkdtemp',
        'webbrowser.open', 'subprocess.Popen',
        'multiprocessing.Process',
        'threading.Thread', '.start()',
        'importlib.import_module',
        'pkgutil.', 'imp.', 'zipfile.',
        'tarfile.', 'shutil.make_archive',
        'os.walk("/")', 'os.listdir("/")',
        'os.scandir("/")', 'glob.glob("/")',
        'pathlib.Path("/")',
    ]

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            content_lower = content.lower()

        for pattern in critical_patterns:
            if pattern.lower() in content_lower:
                return False, f"تهديد أمني: تم اكتشاف {pattern}"

        # فحص حجم الملف
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            return False, f"الملف كبير جداً - يتجاوز حد {MAX_FILE_SIZE // (1024*1024)} ميجابايت"

        # فحص عدد السطور
        line_count = content.count('\n')
        if line_count > 5000:
            return False, f"الكود طويل جداً - يتجاوز 5000 سطر"

        return True, "الكود آمن"
    except Exception as e:
        return False, f"خطأ في فحص الملف: {e}"

# --- تثبيت التبعيات تلقائياً ---
def auto_install_dependencies(file_path):
    installations = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        python_packages = {
            'requests': 'requests',
            'flask': 'flask',
            'django': 'django',
            'numpy': 'numpy',
            'pandas': 'pandas',
            'matplotlib': 'matplotlib',
            'scipy': 'scipy',
            'sklearn': 'scikit-learn',
            'cv2': 'opencv-python',
            'PIL': 'Pillow',
            'bs4': 'beautifulsoup4',
            'selenium': 'selenium',
            'telebot': 'pyTelegramBotAPI',
            'telegram': 'python-telegram-bot',
            'pyrogram': 'pyrogram',
            'tgcrypto': 'TgCrypto',
            'aiohttp': 'aiohttp',
            'asyncio': 'asyncio',
            'pymongo': 'pymongo',
            'redis': 'redis',
            'mysql': 'mysql-connector-python',
        }
        
        import_pattern = r'(?:from\s+(\w+)|import\s+(\w+))'
        matches = re.findall(import_pattern, content)
        
        installed_packages = set()
        for match in matches:
            module = match[0] or match[1]
            if module in python_packages and module not in installed_packages:
                try:
                    # تحقق إذا كانت المكتبة مثبتة بالفعل
                    result_check = subprocess.run(
                        [sys.executable, '-m', 'pip', 'show', python_packages[module]], 
                        capture_output=True, text=True
                    )
                    
                    if result_check.returncode != 0:
                        # تثبيت المكتبة
                        result = subprocess.run(
                            [sys.executable, '-m', 'pip', 'install', python_packages[module]], 
                            capture_output=True, text=True, timeout=120
                        )
                        if result.returncode == 0:
                            installations.append(f"✅ تم تثبيت: {python_packages[module]}")
                        else:
                            installations.append(f"❌ فشل التثبيت: {python_packages[module]}")
                    else:
                        installations.append(f"✅ مسبقاً: {python_packages[module]}")
                    
                    installed_packages.add(module)
                except Exception as e:
                    installations.append(f"❌ خطأ في التثبيت {python_packages[module]}: {str(e)}")
    
    except Exception as e:
        installations.append(f"❌ خطأ في تحليل التبعيات: {str(e)}")
    
    return installations

# --- التحقق من موارد النظام ---
def check_system_resources():
    """التحقق من توفر الموارد"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        if cpu_percent > 85:
            return False, f"استخدام المعالج مرتفع جداً: {cpu_percent}%"
        if memory.percent > 90:
            return False, f"الذاكرة شبه ممتلئة: {memory.percent}%"
        
        # التحقق من عدد العمليات النشطة
        running_scripts = sum(1 for script in bot_scripts.values() 
                            if script.get('process') and is_bot_running(script['user_id'], script['file_name']))
        
        if running_scripts >= MAX_CONCURRENT_SCRIPTS:
            return False, f"تم الوصول للحد الأقصى للعمليات: {running_scripts}/{MAX_CONCURRENT_SCRIPTS}"
        
        return True, "الموارد متاحة"
    except Exception as e:
        return False, f"خطأ في فحص الموارد: {e}"

# --- تشغيل السكربت (معدل لنظام السجلات الجديد) ---
def execute_script(user_id, script_path, message_for_updates=None):
    """تشغيل سكربت بايثون مع إدارة السجلات الموفرة للمساحة"""
    script_name = os.path.basename(script_path)
    script_name_no_ext = os.path.splitext(script_name)[0]
    script_key = f"{user_id}_{script_name}"

    try:
        # التحقق من الموارد
        resource_ok, resource_msg = check_system_resources()
        if not resource_ok:
            if message_for_updates:
                safe_edit_message(
                    message_for_updates.chat.id,
                    message_for_updates.message_id,
                    f"⚠️ لا يمكن تشغيل السكربت\n{resource_msg}"
                )
            return False, resource_msg

        if message_for_updates:
            safe_edit_message(
                message_for_updates.chat.id,
                message_for_updates.message_id,
                f"🐍 جاري معالجة ملف بايثون\nالملف: {script_name}\nالحالة: جاري التحليل..."
            )

        # تثبيت التبعيات
        if message_for_updates:
            safe_edit_message(
                message_for_updates.chat.id,
                message_for_updates.message_id,
                f"🐍 جاري تشغيل السكربت...\nالملف: {script_name}\nالحالة: جاري تثبيت المكتبات..."
            )

        installations = auto_install_dependencies(script_path)
        
        if installations and message_for_updates:
            install_msg = "🐍 تثبيت المكتبات:\n\n" + "\n".join(installations[:5])
            if len(installations) > 5:
                install_msg += f"\n... و {len(installations) - 5} أخرى"
            safe_send_message(message_for_updates.chat.id, install_msg)

        # إنشاء ملف السجل (أو الكتابة فوقه)
        log_file_name = f"exec_{user_id}_{script_name_no_ext}.log"
        log_file_path = os.path.join(LOGS_DIR, log_file_name)

        # فتح الملف بوضع 'w' ليقوم بمسح المحتوى القديم وكتابة الجديد
        with open(log_file_path, 'w', encoding='utf-8') as log_file:
            # إضافة طابع زمني لبداية التشغيل
            log_file.write(f"--- Start Log: {datetime.now()} ---\n\n")
            
            process = subprocess.Popen(
                [sys.executable, script_path],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=os.path.dirname(script_path), 
                env=os.environ.copy()
            )

            # حفظ معلومات العملية
            bot_scripts[script_key] = {
                'process': process,
                'script_key': script_key,
                'user_id': user_id,
                'file_name': script_name,
                'start_time': datetime.now(),
                'log_file_path': log_file_path
            }

            # رسالة النجاح
            if message_for_updates:
                success_msg = f"🐍 تم تشغيل سكربت بايثون بنجاح!\n\n"
                success_msg += f"الملف: {script_name}\n"
                success_msg += f"معرف العملية: {process.pid}\n"
                success_msg += f"الحالة: قيد التشغيل\n"
                success_msg += f"⏱️ المدة القصوى: {MAX_SCRIPT_RUNTIME//60} دقيقة"

                safe_edit_message(
                    message_for_updates.chat.id, 
                    message_for_updates.message_id, 
                    success_msg
                )

            return True, f"تم بدء السكربت برقم {process.pid}"

    except Exception as e:
        error_msg = f"فشل التشغيل: {str(e)}"
        logger.error(f"خطأ في تشغيل السكربت للمستخدم {user_id}: {e}")

        if message_for_updates:
            safe_edit_message(
                message_for_updates.chat.id, 
                message_for_updates.message_id, 
                f"❌ {error_msg}"
            )

        return False, error_msg

# --- معالجات الأوامر ---
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    if user_id not in admin_ids:
        safe_reply_to(message, "🚫 عذراً، هذا البوت متاح للمشرفين فقط!")
        return

    user_name = message.from_user.first_name or "المستخدم"

    welcome_msg = f"🐍 بوت استضافة بايثون\n\n"
    welcome_msg += f"👋 مرحباً {user_name}!\n\n"
    welcome_msg += f"🔐 الميزات:\n"
    welcome_msg += f"✅ استضافة ملفات بايثون\n"
    welcome_msg += f"🚀 تشغيل الأكواد\n"
    welcome_msg += f"🛡️ فحص أمني متقدم\n"
    welcome_msg += f"🌐 مراقبة فورية\n"
    welcome_msg += f"📊 إدارة العمليات\n"
    welcome_msg += f"⚡ تثبيت تلقائي للمكتبات\n"
    welcome_msg += f"📚 إدارة يدوية للمكتبات\n\n"
    welcome_msg += f"📊 حالتك:\n"
    welcome_msg += f"📄 الملفات الحالية: {len(user_files.get(user_id, []))} ملف\n"
    welcome_msg += f"👤 نوع الحساب: {'👑 المالك' if user_id == OWNER_ID else '👑 مشرف'}\n\n"
    welcome_msg += f"💡 ابدأ بسرعة: ارفع أي ملف بايثون!"

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for row in ADMIN_BUTTONS:
        markup.add(*[types.KeyboardButton(text) for text in row])

    safe_send_message(message.chat.id, welcome_msg, reply_markup=markup)

@bot.message_handler(content_types=['document'])
def handle_file_upload(message):
    user_id = message.from_user.id
    if user_id not in admin_ids:
        safe_reply_to(message, "🚫 عذراً، هذا البوت متاح للمشرفين فقط!")
        return

    file_info = bot.get_file(message.document.file_id)
    file_name = message.document.file_name or f"file_{int(time.time())}.py"
    file_ext = os.path.splitext(file_name)[1].lower()

    if file_ext != '.py':
        safe_reply_to(message, "❌ عذراً! هذا البوت يدعم ملفات بايثون (.py) فقط!")
        return

    if message.document.file_size > MAX_FILE_SIZE:
        safe_reply_to(message, f"❌ الملف كبير جداً! الحد الأقصى {MAX_FILE_SIZE // (1024*1024)} ميجابايت")
        return

    try:
        processing_msg = safe_reply_to(message, f"🔍 جاري الفحص الأمني لـ {file_name}...")

        if file_info.file_path is None:
            safe_reply_to(message, "❌ فشل تنزيل الملف\n\nتعذر الحصول على مسار الملف")
            return
        downloaded_file = bot.download_file(file_info.file_path)

        script_folder = get_script_folder(user_id, file_name)
        temp_file_path = os.path.join(script_folder, f"temp_{file_name}")
        
        with open(temp_file_path, 'wb') as f:
            f.write(downloaded_file)

        # الجميع يخضع للفحص الأمني
        safe_edit_message(processing_msg.chat.id, processing_msg.message_id, 
                         f"🛡️ الفحص الأمني: {file_name}...")

        is_safe, scan_result = check_malicious_code(temp_file_path)
        
        if not is_safe:
            try:
                os.remove(temp_file_path)
            except:
                pass
            
            logger.warning(f"انتهاك أمني: المستخدم {user_id} رفع ملف بأوامر نظام: {file_name} - {scan_result}")
            
            alert_msg = f"🚨 تم حظر الرفع 🚨\n\n"
            alert_msg += f"❌ تم اكتشاف أمر نظام!\n"
            alert_msg += f"📄 الملف: {file_name}\n"
            alert_msg += f"🔍 المشكلة: {scan_result}\n\n"
            alert_msg += f"💡 فقط أوامر النظام والأنماط الخبيثة محظورة.\n"
            alert_msg += f"أكواد البرمجة العادية مسموحة!"
            
            safe_edit_message(processing_msg.chat.id, processing_msg.message_id, alert_msg)
            return

        # التحقق من عدد الملفات للمستخدم
        if user_id in user_files and len(user_files[user_id]) >= MAX_TOTAL_SCRIPTS_PER_USER:
            safe_edit_message(processing_msg.chat.id, processing_msg.message_id,
                            f"❌ تجاوزت الحد المسموح\n\nلقد وصلت للحد الأقصى ({MAX_TOTAL_SCRIPTS_PER_USER}) ملف.\nحذف بعض الملفات القديمة أولاً.")
            os.remove(temp_file_path)
            return

        file_path = os.path.join(script_folder, file_name)
        try:
            shutil.move(temp_file_path, file_path)
        except:
            os.rename(temp_file_path, file_path)

        safe_edit_message(processing_msg.chat.id, processing_msg.message_id, 
                         f"✅ تم اجتياز الفحص الأمني - جاري معالجة {file_name}...")

        if user_id not in user_files:
            user_files[user_id] = []

        user_files[user_id] = [fn for fn in user_files[user_id] if fn != file_name]
        user_files[user_id].append(file_name)

        try:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO user_files (user_id, file_name) VALUES (?, ?)',
                     (user_id, file_name))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"خطأ في قاعدة البيانات عند حفظ معلومات الملف: {e}")

        success, result = execute_script(user_id, file_path, processing_msg)
        
        if not success:
            success_msg = f"✅ تم رفع {file_name} بنجاح!\n\n"
            success_msg += f"🛡️ الأمان: اجتاز جميع الفحوصات\n"
            success_msg += f"⚠️ مطلوب بدء يدوي للأمان\n\n"
            success_msg += f"استخدم 'ملفاتي' لإدارة ملفك."
            
            safe_edit_message(processing_msg.chat.id, processing_msg.message_id, success_msg)

    except Exception as e:
        logger.error(f"خطأ في رفع الملف: {e}")
        safe_reply_to(message, f"❌ فشل الرفع\n\nخطأ في معالجة الملف: {str(e)}")
        
        try:
            script_folder = get_script_folder(user_id, file_name)
            temp_file_path = os.path.join(script_folder, f"temp_{file_name}")
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        except:
            pass

# --- معالجات الأزرار ---
@bot.message_handler(func=lambda message: message.text == "📤 رفع ملف")
def upload_file_button(message):
    if message.from_user.id not in admin_ids:
        safe_reply_to(message, "🚫 هذا البوت متاح للمشرفين فقط!")
        return
    safe_reply_to(message, f"🐍 رفع ملف بايثون\n\n📁 أرسل لي ملف بايثون (.py) للرفع!\n\n🛡️ جميع الملفات آمنة!\n\n📏 الحد الأقصى: {MAX_FILE_SIZE // (1024*1024)} ميجابايت")

@bot.message_handler(func=lambda message: message.text == "📂 ملفاتي")
def check_files_button(message):
    user_id = message.from_user.id
    if user_id not in admin_ids:
        safe_reply_to(message, "🚫 هذا البوت متاح للمشرفين فقط!")
        return
        
    files = user_files.get(user_id, [])

    if not files:
        safe_reply_to(message, "📂 ملفاتك\n\n🔒 لم يتم رفع أي ملفات بعد.\n\n💡 ارفع ملف بايثون للبدء!")
        return

    files_text = f"🔒 ملفاتك ({len(files)}/{MAX_TOTAL_SCRIPTS_PER_USER}):\n\n📁 اضغط على أي ملف لإدارته:\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)

    for i, file_name in enumerate(files, 1):
        status = "🟢 يعمل" if is_bot_running(user_id, file_name) else "⭕ متوقف"
        icon = "🐍"
        files_text += f"{i}. {file_name}\n   الحالة: {status}\n\n"

        markup.add(types.InlineKeyboardButton(
            f"{icon} {file_name} - {status}", 
            callback_data=f'control_{user_id}_{file_name}'
        ))

    files_text += "⚙️ خيارات الإدارة:\n• 🟢 تشغيل/🔴 إيقاف الملفات\n• 🗑️ حذف الملفات\n• 📜 عرض السجلات\n• 🔄 إعادة تشغيل الملفات"

    safe_reply_to(message, files_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "⚡ سرعة البوت")
def bot_speed_button(message):
    if message.from_user.id not in admin_ids:
        safe_reply_to(message, "🚫 هذا البوت متاح للمشرفين فقط!")
        return
        
    start_time = time.time()
    msg = safe_reply_to(message, "🏃 جاري اختبار السرعة...")
    response_time = round((time.time() - start_time) * 1000, 2)

    # معلومات النظام
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    
    speed_text = f"⚡ أداء بوت استضافة بايثون:\n\n"
    speed_text += f"🚀 وقت الاستجابة: {response_time}ms\n"
    speed_text += f"🖥️ استخدام المعالج: {cpu_percent}%\n"
    speed_text += f"💾 استخدام الذاكرة: {memory.percent}%\n"
    speed_text += f"📊 الملفات النشطة: {sum(1 for s in bot_scripts.values() if s.get('process'))}\n"
    speed_text += f"🔧 السجلات: {len(os.listdir(LOGS_DIR)) if os.path.exists(LOGS_DIR) else 0} ملف\n\n"
    speed_text += f"✅ جميع الأنظمة تعمل!"

    safe_edit_message(msg.chat.id, msg.message_id, speed_text)

@bot.message_handler(func=lambda message: message.text == "📊 الإحصائيات")
def statistics_button(message):
    user_id = message.from_user.id
    if user_id not in admin_ids:
        safe_reply_to(message, "🚫 هذا البوت متاح للمشرفين فقط!")
        return
        
    total_files = sum(len(files) for files in user_files.values())
    
    running_scripts = 0
    for script_key in bot_scripts:
        script_info = bot_scripts[script_key]
        if script_info.get('process') and is_bot_running(script_info['user_id'], script_info['file_name']):
            running_scripts += 1

    stats_text = f"📊 إحصائيات بوت استضافة بايثون:\n\n"
    stats_text += f"👑 المشرفون: {len(admin_ids)}\n"
    stats_text += f"📁 إجمالي الملفات: {total_files}\n"
    stats_text += f"🚀 السكربتات النشطة: {running_scripts}/{MAX_CONCURRENT_SCRIPTS}\n"
    stats_text += f"🔧 ملفاتك: {len(user_files.get(user_id, []))}/{MAX_TOTAL_SCRIPTS_PER_USER}\n\n"
    stats_text += f"🔒 القيود:\n"
    stats_text += f"📏 حجم الملف: {MAX_FILE_SIZE // (1024*1024)} ميجابايت\n"
    stats_text += f"⏱️ مدة التشغيل: {MAX_SCRIPT_RUNTIME//60} دقيقة\n"
    stats_text += f"🔢 العمليات المتزامنة: {MAX_CONCURRENT_SCRIPTS}\n"
    stats_text += f"📁 الملفات لكل مستخدم: {MAX_TOTAL_SCRIPTS_PER_USER}"

    safe_reply_to(message, stats_text)

@bot.message_handler(func=lambda message: message.text == "🟢 الملفات النشطة")
def running_code_button(message):
    user_id = message.from_user.id
    if user_id not in admin_ids:
        safe_reply_to(message, "🚫 هذا البوت متاح للمشرفين فقط!")
        return

    active_scripts_info = []
    for script_key, script_info in bot_scripts.items():
        if script_info.get('process') and is_bot_running(script_info['user_id'], script_info['file_name']):
            active_scripts_info.append(script_info)

    if not active_scripts_info:
        safe_reply_to(message, "🟢 مراقبة الملفات النشطة\n\n📊 لا توجد سكربتات قيد التشغيل حالياً.\n\n💡 جميع الأنظمة خاملة.")
        return

    running_text = f"🟢 مراقبة الملفات النشطة\n\n"
    running_text += f"📊 السكربتات النشطة: {len(active_scripts_info)}/{MAX_CONCURRENT_SCRIPTS}\n\n"

    for script_info in active_scripts_info:
        user_id_script = script_info['user_id']
        file_name = script_info['file_name']
        start_time = script_info['start_time'].strftime("%H:%M:%S")
        
        running_text += f"🐍 {file_name}\n"
        running_text += f"👤 المستخدم: {user_id_script}\n"
        running_text += f"⏰ بدأ: {start_time}\n"
        running_text += f"🆔 رقم العملية: {script_info['process'].pid}\n\n"

    safe_reply_to(message, running_text)

# *** قسم إدارة المكاتب ***
@bot.message_handler(func=lambda message: message.text == "📚 المكاتب")
def handle_libraries_menu(message):
    if message.from_user.id not in admin_ids:
        safe_reply_to(message, "🚫 هذا البوت متاح للمشرفين فقط!")
        return
        
    text = "📚 إدارة المكاتب\n\n"
    text += "هنا يمكنك تثبيت، عرض، أو حذف مكاتب بايثون (pip) يدوياً.\n\n"
    text += "⚠️ ملحوظة: المكتبات الأساسية للبوت محمية ضد الحذف."
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ إضافة مكتبة", callback_data="lib_add"),
        types.InlineKeyboardButton("📋 عرض المكاتب", callback_data="lib_list"),
        types.InlineKeyboardButton("🗑️ حذف مكتبة", callback_data="lib_delete")
    )
    
    safe_reply_to(message, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ['lib_add', 'lib_list', 'lib_delete'])
def handle_library_callbacks(call):
    try:
        if call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, "🚫 الوصول مرفوض!")
            return

        if call.data == 'lib_add':
            bot.answer_callback_query(call.id, "أرسل اسم المكتبة للتثبيت")
            msg = bot.send_message(call.message.chat.id, "📝 من فضلك أرسل الآن اسم المكتبة التي تريد تثبيتها (مثل: `requests`):", parse_mode='Markdown', reply_markup=types.ForceReply(selective=False))
            bot.register_next_step_handler(msg, handle_add_library)
            
        elif call.data == 'lib_list':
            bot.answer_callback_query(call.id, "🔄 جاري جلب القائمة...")
            msg = safe_edit_message(call.message.chat.id, call.message.message_id, "🔄 جاري جلب قائمة المكاتب المثبتة `(pip freeze)`...")
            
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'freeze'],
                    capture_output=True, text=True, timeout=30
                )
                
                if result.returncode == 0:
                    output = result.stdout
                    if len(output) > 3500:
                        output = output[:3500] + "\n... (القائمة طويلة جداً)"
                    safe_edit_message(msg.chat.id, msg.message_id, f"📋 المكاتب المثبتة حالياً:\n\n```{output}```", parse_mode='Markdown')
                else:
                    safe_edit_message(msg.chat.id, msg.message_id, f"❌ فشل عرض المكاتب:\n\n{result.stderr}")
            
            except Exception as e:
                safe_edit_message(msg.chat.id, msg.message_id, f"❌ حدث خطأ أثناء عرض المكاتب:\n{str(e)}")

        elif call.data == 'lib_delete':
            bot.answer_callback_query(call.id, "أرسل اسم المكتبة للحذف")
            msg = bot.send_message(call.message.chat.id, "🗑️ من فضلك أرسل الآن اسم المكتبة التي تريد حذفها (مثل: `numpy`):", parse_mode='Markdown', reply_markup=types.ForceReply(selective=False))
            bot.register_next_step_handler(msg, handle_delete_library)

    except Exception as e:
        logger.error(f"خطأ في معالج المكاتب: {e}")
        bot.answer_callback_query(call.id, "❌ حدث خطأ!")

def handle_add_library(message):
    try:
        if message.from_user.id not in admin_ids: return
        
        library_name = message.text.strip().split(" ")[0]
        if not library_name:
            safe_reply_to(message, "❌ لم يتم إرسال اسم. تم الإلغاء.")
            return

        # التحقق من المكتبات المحظورة
        if library_name.lower() in BANNED_PACKAGES:
            safe_reply_to(message, f"🚫 **ممنوع!**\nالمكتبة `{library_name}` محظورة لأسباب أمنية.", parse_mode='Markdown')
            return

        msg = safe_reply_to(message, f"🔄 جاري تثبيت `{library_name}`... قد يستغرق هذا بعض الوقت...", parse_mode='Markdown')

        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', library_name],
                capture_output=True, text=True, timeout=120
            )
            
            if result.returncode == 0:
                safe_edit_message(msg.chat.id, msg.message_id, f"✅ تم تثبيت `{library_name}` بنجاح!\n\n`{result.stdout[-1000:]}`", parse_mode='Markdown')
            else:
                safe_edit_message(msg.chat.id, msg.message_id, f"❌ فشل تثبيت `{library_name}`:\n\n{result.stderr}", parse_mode='Markdown')
        
        except Exception as e:
            safe_edit_message(msg.chat.id, msg.message_id, f"❌ حدث خطأ أثناء تثبيت `{library_name}`:\n{str(e)}", parse_mode='Markdown')

    except Exception as e:
        logger.error(f"خطأ في إضافة مكتبة: {e}")
        safe_reply_to(message, "❌ حدث خطأ فادح.")

def handle_delete_library(message):
    try:
        if message.from_user.id not in admin_ids: return
        
        library_name = message.text.strip().split(" ")[0].lower()
        if not library_name:
            safe_reply_to(message, "❌ لم يتم إرسال اسم. تم الإلغاء.")
            return

        if library_name in PROTECTED_PACKAGES:
            safe_reply_to(message, f"🛡️ **محمي!**\nلا يمكن حذف المكتبة `{library_name}` لأنها ضرورية لعمل البوت.", parse_mode='Markdown')
            return

        msg = safe_reply_to(message, f"🔄 جاري حذف `{library_name}`...", parse_mode='Markdown')

        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'uninstall', '-y', library_name],
                capture_output=True, text=True, timeout=60
            )
            
            if result.returncode == 0:
                safe_edit_message(msg.chat.id, msg.message_id, f"🗑️ تم حذف `{library_name}` بنجاح!", parse_mode='Markdown')
            else:
                safe_edit_message(msg.chat.id, msg.message_id, f"❌ فشل حذف `{library_name}`:\n\n{result.stderr}", parse_mode='Markdown')
        
        except Exception as e:
            safe_edit_message(msg.chat.id, msg.message_id, f"❌ حدث خطأ أثناء حذف `{library_name}`:\n{str(e)}", parse_mode='Markdown')

    except Exception as e:
        logger.error(f"خطأ في حذف مكتبة: {e}")
        safe_reply_to(message, "❌ حدث خطأ فادح.")

@bot.message_handler(func=lambda message: message.text == "📞 تواصل")
def contact_owner_button(message):
    if message.from_user.id not in admin_ids:
        safe_reply_to(message, "🚫 هذا البوت متاح للمشرفين فقط!")
        return
        
    safe_reply_to(message, f"📞 التواصل مع المالك\n\n👤 المالك: @llllllIlIlIlIlIlIlIl\n\n💬 للدعم والاستفسارات!")

# --- معالجات أزرار التحكم ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('control_'))
def handle_file_control(call):
    try:
        parts = call.data.split('_', 2)
        if len(parts) != 3:
            bot.answer_callback_query(call.id, "❌ بيانات الزر غير صالحة")
            return
            
        _, user_id_str, file_name = parts
        user_id = int(user_id_str)
        
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, "🚫 الوصول مرفوض!")
            return
            
        user_files_list = user_files.get(user_id, [])
        
        if file_name not in user_files_list:
            bot.answer_callback_query(call.id, "❌ الملف غير موجود!")
            call.data = f'back_files_{user_id}'
            handle_back_to_files(call)
            return
        
        markup = types.InlineKeyboardMarkup(row_width=3)
        
        is_running = is_bot_running(user_id, file_name)
        
        if is_running:
            markup.add(
                types.InlineKeyboardButton("🔴 إيقاف", callback_data=f'stop_{user_id}_{file_name}'),
                types.InlineKeyboardButton("🔄 إعادة تشغيل", callback_data=f'restart_{user_id}_{file_name}')
            )
        else:
            markup.add(
                types.InlineKeyboardButton("🟢 تشغيل", callback_data=f'start_{user_id}_{file_name}')
            )
        
        markup.add(
            types.InlineKeyboardButton("📜 السجلات", callback_data=f'logs_{user_id}_{file_name}'),
            types.InlineKeyboardButton("✏️ تعديل", callback_data=f'edit_{user_id}_{file_name}'),
            types.InlineKeyboardButton("🗑️ حذف", callback_data=f'delete_{user_id}_{file_name}')
        )

        markup.add(
            types.InlineKeyboardButton("🔙 رجوع", callback_data=f'back_files_{user_id}')
        )
        
        status = "🟢 يعمل" if is_running else "⭕ متوقف"
        
        control_text = f"🔧 لوحة التحكم بالملف\n\n"
        control_text += f"📄 الملف: {file_name}\n"
        control_text += f"📁 النوع: بايثون\n"
        control_text += f"🔄 الحالة: {status}\n"
        control_text += f"👤 المالك: {user_id}\n\n"
        control_text += f"🎛️ اختر إجراءً:"
        
        safe_edit_message(
            call.message.chat.id,
            call.message.message_id,
            control_text,
            reply_markup=markup
        )
        
        bot.answer_callback_query(call.id, f"لوحة التحكم لـ {file_name}")
        
    except Exception as e:
        logger.error(f"خطأ في معالج التحكم بالملفات: {e}")
        bot.answer_callback_query(call.id, "❌ حدث خطأ!")

@bot.callback_query_handler(func=lambda call: call.data.startswith('start_'))
def handle_start_file(call):
    try:
        parts = call.data.split('_', 2)
        user_id = int(parts[1])
        file_name = parts[2]
        
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, "🚫 الوصول مرفوض!")
            return
            
        script_folder = get_script_folder(user_id, file_name)
        file_path = os.path.join(script_folder, file_name)
        
        if not os.path.exists(file_path):
            bot.answer_callback_query(call.id, "❌ الملف غير موجود!")
            return
            
        if is_bot_running(user_id, file_name):
            bot.answer_callback_query(call.id, "⚠️ يعمل بالفعل!")
            return
            
        bot.answer_callback_query(call.id, "🔄 جاري التشغيل...")
        success, result = execute_script(user_id, file_path)
        
        if success:
            bot.answer_callback_query(call.id, "🟢 تم التشغيل بنجاح!")
            call.data = f'control_{user_id}_{file_name}'
            handle_file_control(call)
        else:
            bot.answer_callback_query(call.id, f"❌ فشل التشغيل: {result}")
            
    except Exception as e:
        logger.error(f"خطأ في تشغيل الملف: {e}")
        bot.answer_callback_query(call.id, "❌ حدث خطأ!")

@bot.callback_query_handler(func=lambda call: call.data.startswith('stop_'))
def handle_stop_file(call):
    try:
        parts = call.data.split('_', 2)
        user_id = int(parts[1])
        file_name = parts[2]
        
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, "🚫 الوصول مرفوض!")
            return
            
        script_key = f"{user_id}_{file_name}"
        script_info = bot_scripts.get(script_key)
        
        if script_info and script_info.get('process'):
            try:
                process = script_info['process']
                process.terminate()
                process.wait(timeout=5)
                script_info['process'] = None
                
                bot.answer_callback_query(call.id, "🔴 تم الإيقاف بنجاح!")
                call.data = f'control_{user_id}_{file_name}'
                handle_file_control(call)
            except Exception as e:
                script_info['process'] = None
                bot.answer_callback_query(call.id, f"⚠️ تحذير: {str(e)}")
                call.data = f'control_{user_id}_{file_name}'
                handle_file_control(call)
        else:
            bot.answer_callback_query(call.id, "⚠️ غير قيد التشغيل!")
            
    except Exception as e:
        logger.error(f"خطأ في إيقاف الملف: {e}")
        bot.answer_callback_query(call.id, "❌ حدث خطأ!")

@bot.callback_query_handler(func=lambda call: call.data.startswith('restart_'))
def handle_restart_file(call):
    try:
        parts = call.data.split('_', 2)
        user_id = int(parts[1])
        file_name = parts[2]
        
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, "🚫 الوصول مرفوض!")
            return
            
        script_key = f"{user_id}_{file_name}"
        script_info = bot_scripts.get(script_key)
        
        if script_info and script_info.get('process'):
            try:
                process = script_info['process']
                process.terminate()
                process.wait(timeout=5)
            except:
                pass 
            script_info['process'] = None 
        
        script_folder = get_script_folder(user_id, file_name)
        file_path = os.path.join(script_folder, file_name)
        
        if os.path.exists(file_path):
            bot.answer_callback_query(call.id, "🔄 جاري إعادة التشغيل...")
            success, result = execute_script(user_id, file_path)
            
            if success:
                bot.answer_callback_query(call.id, "🔄 تمت إعادة التشغيل بنجاح!")
                call.data = f'control_{user_id}_{file_name}'
                handle_file_control(call)
            else:
                bot.answer_callback_query(call.id, f"❌ فشلت إعادة التشغيل: {result}")
        else:
            bot.answer_callback_query(call.id, "❌ الملف غير موجود!")
            
    except Exception as e:
        logger.error(f"خطأ في إعادة تشغيل الملف: {e}")
        bot.answer_callback_query(call.id, "❌ حدث خطأ!")

@bot.callback_query_handler(func=lambda call: call.data.startswith('logs_'))
def handle_show_logs(call):
    try:
        parts = call.data.split('_', 2)
        user_id = int(parts[1])
        file_name = parts[2]
        
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, "🚫 الوصول مرفوض!")
            return
            
        script_key = f"{user_id}_{file_name}"
        script_info = bot_scripts.get(script_key)
        
        # البحث عن السجل باستخدام الاسم الثابت إذا لم يكن في الذاكرة
        if script_info and 'log_file_path' in script_info:
             log_file_path = script_info['log_file_path']
        else:
             # محاولة تخمين المسار إذا لم يكن السكربت يعمل حالياً
             script_name_no_ext = os.path.splitext(file_name)[0]
             log_file_path = os.path.join(LOGS_DIR, f"exec_{user_id}_{script_name_no_ext}.log")

        if os.path.exists(log_file_path):
            try:
                with open(log_file_path, 'r', encoding='utf-8') as f:
                    logs = f.read()
                
                if logs.strip():
                    if len(logs) > 4000:
                        logs = "..." + logs[-4000:]
                    
                    logs_text = f"📜 سجلات التشغيل - {file_name}\n\n```\n{logs}\n```"
                else:
                    logs_text = f"📜 سجلات التشغيل - {file_name}\n\n🔇 لا توجد مخرجات بعد"
                    
                bot.send_message(call.message.chat.id, logs_text, parse_mode='Markdown')
                bot.answer_callback_query(call.id, "📜 تم إرسال السجلات!")
                
            except Exception as e:
                bot.answer_callback_query(call.id, f"❌ خطأ في قراءة السجلات: {str(e)}")
        else:
            bot.answer_callback_query(call.id, "❌ لا يوجد ملف سجل لهذا السكربت حتى الآن.")
            
    except Exception as e:
        logger.error(f"خطأ في عرض السجلات: {e}")
        bot.answer_callback_query(call.id, "❌ حدث خطأ!")

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def handle_edit_file(call):
    try:
        parts = call.data.split('_', 2)
        user_id = int(parts[1])
        file_name = parts[2]
        
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, "🚫 الوصول مرفوض!")
            return

        script_folder = get_script_folder(user_id, file_name)
        file_path = os.path.join(script_folder, file_name)
        
        if not os.path.exists(file_path):
            bot.answer_callback_query(call.id, "❌ الملف غير موجود!")
            return
            
        bot.answer_callback_query(call.id, "📤 يرجى إرسال الملف المعدل")
        
        msg_text = f"✏️ **تعديل الملف: `{file_name}`**\n\n"
        msg_text += "لتعديل هذا الملف، يرجى إرسال ملف البايثون (`.py`) المعدل الآن.\n\n"
        msg_text += f"سيتم استبدال الملف القديم بالملف الجديد الذي سترسله."
        
        msg = bot.send_message(call.message.chat.id, msg_text, parse_mode='Markdown', reply_markup=types.ForceReply(selective=False))

        bot.register_next_step_handler(msg, process_edited_file_upload, user_id, file_name, file_path)

    except Exception as e:
        logger.error(f"خطأ في بدء تعديل الملف: {e}")
        bot.answer_callback_query(call.id, "❌ حدث خطأ!")

def process_edited_file_upload(message, user_id, file_name, file_path):
    try:
        if message.document is None:
            safe_reply_to(message, "❌ تم الإلغاء. يرجى إرسال **ملف (document)** وليس رسالة نصية.")
            return

        if not message.document.file_name.lower().endswith('.py'):
            safe_reply_to(message, "❌ ملف غير صالح! يرجى إرسال ملف `.py` فقط.")
            return

        new_file_info = bot.get_file(message.document.file_id)
        
        processing_msg = safe_reply_to(message, f"🔍 جاري فحص الملف المعدل `{message.document.file_name}`...")

        downloaded_file = bot.download_file(new_file_info.file_path)

        temp_edit_path = file_path + ".temp_edit"
        with open(temp_edit_path, 'wb') as f:
            f.write(downloaded_file)
            
        # الجميع يخضع للفحص الأمني
        is_safe, scan_result = check_malicious_code(temp_edit_path)
            
        if not is_safe:
            os.remove(temp_edit_path)
            alert_msg = f"🚨 تم رفض التعديل 🚨\n\n"
            alert_msg += f"❌ تم اكتشاف أمر نظام في التعديل!\n"
            alert_msg += f"🔍 المشكلة: {scan_result}\n\n"
            alert_msg += f"لم يتم حفظ التغييرات."
            safe_edit_message(processing_msg.chat.id, processing_msg.message_id, alert_msg)
            return
            
        script_key = f"{user_id}_{file_name}"
        if is_bot_running(user_id, file_name):
            script_info = bot_scripts.get(script_key)
            if script_info and script_info.get('process'):
                try:
                    script_info['process'].terminate()
                    script_info['process'] = None
                except:
                    pass 
        
        shutil.move(temp_edit_path, file_path)
        
        success_msg = f"✅ **تم حفظ التعديلات**\n\n"
        success_msg += f"📄 الملف: `{file_name}`\n"
        success_msg += f"🛡️ الأمان: اجتاز الفحص\n"
        
        safe_edit_message(processing_msg.chat.id, processing_msg.message_id, success_msg + "\n🔄 جاري محاولة إعادة تشغيل السكربت...", parse_mode='Markdown')
        
        success, result = execute_script(user_id, file_path)
        if success:
            bot.send_message(message.chat.id, f"🟢 تم إعادة تشغيل `{file_name}` بنجاح!", parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, f"⚠️ تم حفظ الملف، لكن فشلت إعادة التشغيل التلقائي.\n{result}\n\nيمكنك تشغيله يدوياً من 'ملفاتي'.")

    except Exception as e:
        logger.error(f"خطأ في معالجة الملف المعدل المرفوع: {e}")
        safe_reply_to(message, f"❌ حدث خطأ فادح أثناء حفظ التعديل: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def handle_delete_file(call):
    try:
        parts = call.data.split('_', 2)
        user_id = int(parts[1])
        file_name = parts[2]
        
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, "🚫 الوصول مرفوض!")
            return
            
        script_key = f"{user_id}_{file_name}"
        
        if script_key in bot_scripts and bot_scripts[script_key].get('process'):
            try:
                process = bot_scripts[script_key]['process']
                process.terminate()
            except:
                pass
        
        if script_key in bot_scripts:
            try:
                # محاولة حذف السجل المرتبط عند حذف الملف
                script_name_no_ext = os.path.splitext(file_name)[0]
                log_path = os.path.join(LOGS_DIR, f"exec_{user_id}_{script_name_no_ext}.log")
                if os.path.exists(log_path):
                    os.remove(log_path)
            except Exception as e:
                logger.warning(f"لم نتمكن من حذف ملف السجل: {e}")
            
            del bot_scripts[script_key]
        
        script_folder = get_script_folder(user_id, file_name)
        if os.path.exists(script_folder):
            try:
                shutil.rmtree(script_folder)
            except Exception as e:
                logger.error(f"خطأ في حذف مجلد السكربت {script_folder}: {e}")
        
        if user_id in user_files:
            user_files[user_id] = [fn for fn in user_files[user_id] if fn != file_name]
        
        try:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', (user_id, file_name))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"خطأ في قاعدة البيانات عند حذف الملف: {e}")
        
        bot.answer_callback_query(call.id, f"🗑️ تم حذف {file_name} وكل ملفاته المرتبطة!")
        
        call.data = f'back_files_{user_id}'
        handle_back_to_files(call)
        
    except Exception as e:
        logger.error(f"خطأ في حذف الملف: {e}")
        bot.answer_callback_query(call.id, "❌ حدث خطأ!")

@bot.callback_query_handler(func=lambda call: call.data.startswith('back_files_'))
def handle_back_to_files(call):
    try:
        parts = call.data.split('_', 2)
        user_id = int(parts[2])
        
        files = user_files.get(user_id, [])
        
        if not files:
            files_text = "📂 ملفاتك\n\n🔒 لم يتم رفع أي ملفات بعد.\n\n💡 ارفع ملف بايثون للبدء!"
            markup = None
        else:
            files_text = f"🔒 ملفاتك ({len(files)}/{MAX_TOTAL_SCRIPTS_PER_USER}):\n\n📁 اضغط على أي ملف لإدارته:\n\n"
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            for i, file_name in enumerate(files, 1):
                status = "🟢 يعمل" if is_bot_running(user_id, file_name) else "⭕ متوقف"
                icon = "🐍"
                files_text += f"{i}. {file_name}\n   الحالة: {status}\n\n"
                
                markup.add(types.InlineKeyboardButton(
                    f"{icon} {file_name} - {status}", 
                    callback_data=f'control_{user_id}_{file_name}'
                ))
            
            files_text += "⚙️ خيارات الإدارة:\n• 🟢 تشغيل/🔴 إيقاف الملفات\n• 🗑️ حذف الملفات\n• 📜 عرض السجلات\n• 🔄 إعادة تشغيل الملفات"
        
        safe_edit_message(
            call.message.chat.id,
            call.message.message_id,
            files_text,
            reply_markup=markup
        )
        
        bot.answer_callback_query(call.id, "📂 تم تحديث قائمة الملفات!")
        
    except Exception as e:
        logger.error(f"خطأ في الرجوع للملفات: {e}")
        bot.answer_callback_query(call.id, "❌ حدث خطأ!")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    if message.from_user.id not in admin_ids:
        safe_reply_to(message, "🚫 عذراً، هذا البوت متاح للمشرفين فقط!")
    else:
        safe_reply_to(message, "🔒 استخدم أزرار القائمة أو أرسل /start للمساعدة.")

def cleanup_on_exit():
    """دالة التنظيف عند الإغلاق"""
    logger.info("جاري التنظيف عند الإغلاق...")
    for script_key, script_info in bot_scripts.items():
        try:
            process = script_info.get('process')
            if process and process.poll() is None:
                process.terminate()
                logger.info(f"تم إنهاء السكربت: {script_key}")
        except Exception as e:
            logger.error(f"خطأ في إنهاء السكربت {script_key}: {e}")

# --- روتين مراقبة الموارد ---
def monitor_resources():
    """مراقبة موارد النظام بانتظام"""
    while True:
        try:
            cpu_percent = psutil.cpu_percent(interval=30)
            memory = psutil.virtual_memory()
            
            if cpu_percent > 90 or memory.percent > 95:
                logger.warning(f"تحذير: موارد النظام مرتفعة - CPU: {cpu_percent}%, Memory: {memory.percent}%")
                
                # إيقاف بعض العمليات إذا كانت الموارد مرتفعة جداً
                if cpu_percent > 95 or memory.percent > 98:
                    running_count = sum(1 for s in bot_scripts.values() if s.get('process'))
                    if running_count > 1:
                        # إيقاف أقدم عملية
                        for script_key, script_info in list(bot_scripts.items()):
                            if script_info.get('process'):
                                try:
                                    script_info['process'].terminate()
                                    logger.info(f"تم إيقاف {script_key} بسبب موارد النظام المرتفعة")
                                    break
                                except:
                                    pass
            
            # تنظيف السجلات كل ساعة
            if int(time.time()) % 3600 == 0:
                cleanup_old_logs()
                
        except Exception as e:
            logger.error(f"خطأ في مراقبة الموارد: {e}")
        
        time.sleep(60)  # الانتظار دقيقة بين الفحوصات

# --- بدء البوت ---
if __name__ == "__main__":
    atexit.register(cleanup_on_exit)
    
    init_db()
    load_data()
    
    # تنظيف السجلات القديمة عند البدء
    cleanup_old_logs()
    
    # بدء مراقبة الموارد في خيط منفصل
    import threading
    monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
    monitor_thread.start()
    
    keep_alive()
    
    logger.info("🚀 بوت استضافة بايثون يبدأ...")
    logger.info(f"👑 معرف المالك: {OWNER_ID}")
    logger.info(f"👤 معرف المشرف: {ADMIN_ID}")
    logger.info(f"📁 مجلد الرفع: {UPLOAD_BOTS_DIR}")
    logger.info(f"📏 الحدود: {MAX_CONCURRENT_SCRIPTS} عملية, {MAX_FILE_SIZE//(1024*1024)} ميجابايت")
    
    try:
        bot_info = bot.get_me()
        logger.info(f"البوت متصل بنجاح: @{bot_info.username}")
        print(f"✅ البوت متصل بنجاح: @{bot_info.username}")
        print(f"👑 المالك: {OWNER_ID}")
        print(f"📁 المجلدات: {UPLOAD_BOTS_DIR}, {LOGS_DIR}")
        print(f"🔧 الحدود: {MAX_CONCURRENT_SCRIPTS} عملية, {MAX_FILE_SIZE//(1024*1024)} ميجابايت")
        print("🌐 بدأ سيرفر Flask للحفاظ على الاتصال...")
        
        bot.infinity_polling(timeout=10, long_polling_timeout=5, none_stop=True, interval=0)
    except Exception as e:
        logger.error(f"خطأ في البوت: {e}")
        print(f"❌ فشل اتصال البوت: {e}")
        sys.exit(1)