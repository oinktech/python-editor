from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import time
import sys
import io
import subprocess
import shutil
import psutil
from markupsafe import escape
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired
import os
from dotenv import load_dotenv
from pymongo import MongoClient
import multiprocessing
import concurrent.futures
from flask_cors import CORS

# 加載環境變數
load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = "your_secret_key_here"

# 設定 session 過期時間，假設以秒為單位
SESSION_TIMEOUT = 300

# 表單類，用於輸入 Python 程式碼
class CodeForm(FlaskForm):
    code = TextAreaField('輸入您的 Python 程式碼：', validators=[DataRequired()])
    submit = SubmitField('執行')

# 存儲執行歷史
execution_history = []

# 初始化 MongoDB 連線
def get_db_connection():
    client = MongoClient(os.getenv("MONGODB_URI"))
    db = client.get_database()  # 獲取資料庫，名稱取自 URI
    return db

# 初始化資料庫
def init_db():
    db = get_db_connection()
    db.visitors.create_index("user_id", unique=True)  # 為訪客集合中的 `user_id` 建立唯一索引
    if db.total_visits.count_documents({}) == 0:
        db.total_visits.insert_one({"visit_count": 0})  # 初始化總訪問人數

# 追蹤訪客資料
def track_visitor(ip_address):
    db = get_db_connection()
    user_id = session.get("user_id", str(time.time()))
    session["user_id"] = user_id
    current_time = int(time.time())

    # 更新或新增訪客資料
    db.visitors.update_one(
        {"user_id": user_id},
        {"$set": {"last_seen": current_time, "ip_address": ip_address}},
        upsert=True
    )

    # 清理過期的訪客
    db.visitors.delete_many({"last_seen": {"$lt": current_time - SESSION_TIMEOUT}})

    # 增加歷史訪問人數
    db.total_visits.update_one({}, {"$inc": {"visit_count": 1}})

# 查看當前在線人數
def get_current_visitors():
    db = get_db_connection()
    return db.visitors.count_documents({})

# 查看歷史總訪問人數
def get_total_visits():
    db = get_db_connection()
    visit_data = db.total_visits.find_one()
    return visit_data["visit_count"] if visit_data else 0

# 執行 Python 程式碼的函數
def execute_python(code, user_input=None):
    global execution_history

    # 提取所有需要安裝的模塊
    pip_install_lines = []
    new_code_lines = []

    for line in code.splitlines():
        if line.startswith('!pip install'):
            pip_install_lines.append(line.split(' ')[-1])  # 獲取模塊名稱
        else:
            new_code_lines.append(line)  # 獲取正常程式碼行

    # 安裝所有需要的模塊
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_module = {executor.submit(install_module, module): module for module in pip_install_lines}
        for future in concurrent.futures.as_completed(future_to_module):
            module = future_to_module[future]
            try:
                future.result()
            except Exception as e:
                raise Exception(f"模塊 {module} 安裝失敗：{e}")

    # 合併剩餘的程式碼行
    code_to_execute = '\n'.join(new_code_lines)

    def run_code(output_queue):
        output = ""
        try:
            # 重定向標準輸出與輸入
            stdout = sys.stdout
            sys.stdout = io.StringIO()

            if user_input:
                sys.stdin = io.StringIO(user_input)

            # 特殊命令處理
            if code_to_execute.startswith('!pip uninstall'):
                output = "⚠️由於安全性及相關考量，因此已移除該功能。⚠️"
            elif code_to_execute.startswith('!pip install --upgrade'):
                module = code.split(' ')[-1]
                output = update_module(module)  # 更新模塊並返回信息
            elif code_to_execute.startswith('!pip list'):
                output = list_installed_modules()
            elif code_to_execute.startswith('!'):
                output = "⚠️ 此命令不允許執行。⚠️"
            else:
                exec(code_to_execute)  # 執行過濾後的程式碼
                output = sys.stdout.getvalue()

        except Exception as e:
            output = f"錯誤：{str(e)}"
        
        finally:
            sys.stdout = stdout
            output = escape(output)
            execution_history.append((code, output))
            output_queue.put(output)

    output_queue = multiprocessing.Queue()
    process = multiprocessing.Process(target=run_code, args=(output_queue,))
    process.start()

    # 實時獲取輸出
    while process.is_alive():
        if not output_queue.empty():
            output = output_queue.get()
            return output  # 返回實時輸出
    process.join()

    # 從隊列中獲取最終輸出
    output = output_queue.get()
    return output

# 安裝 Python 模塊
def install_module(module):
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", module], check=True, timeout=60)
        return f"模塊 {module} 安裝成功！"
    except subprocess.CalledProcessError as e:
        raise Exception(f"模塊安裝失敗：{e}")

# 更新 Python 模塊
def update_module(module):
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", module], check=True, timeout=60)
        return f"模塊 {module} 更新成功！"
    except subprocess.CalledProcessError as e:
        raise Exception(f"模塊更新失敗：{e}")

# 列出已安裝的模塊
def list_installed_modules():
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"模塊列出失敗：{e}"

# 獲取系統資源使用情況
@app.route('/get_system_info', methods=['GET'])
def get_system_info():
    # 磁碟使用情況
    total, used, free = shutil.disk_usage("/")
    disk_usage = {
        "total": total // (2**30),  # 將位元組轉換為 GB
        "used": used // (2**30),
        "free": free // (2**30)
    }

    # CPU 使用情況
    cpu_usage = psutil.cpu_percent(interval=1)

    # 記憶體使用情況
    memory = psutil.virtual_memory()
    memory_usage = {
        "total": memory.total // (2**30),
        "used": memory.used // (2**30),
        "free": memory.available // (2**30)
    }

    # 獲取當前在線人數
    current_visitors = get_current_visitors()
    
    # 獲取歷史總訪問人數
    total_visits = get_total_visits()

    return {
        "disk_usage": disk_usage,
        "cpu_usage": cpu_usage,
        "memory_usage": memory_usage,
        "current_visitors": current_visitors,
        "total_visits": total_visits
    }

# 登錄頁面路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == os.getenv('ADMIN_USERNAME') and password == os.getenv('ADMIN_PASSWORD'):
            session['logged_in'] = True
            return redirect(url_for('admin'))

    return render_template('login.html')

# 主頁面路由，處理 Python 程式碼執行
@app.route('/', methods=['GET', 'POST'])
def index():
    form = CodeForm()
    output = None
    ip_address = request.remote_addr  # 獲取訪客的 IP 地址
    track_visitor(ip_address)  # 追蹤訪客資料

    if form.validate_on_submit():
        code = form.code.data
        output = execute_python(code)

    return render_template('index.html', form=form, output=output)

# 管理頁面路由
@app.route('/admin')
def admin():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    system_info = get_system_info()
    current_visitors = get_current_visitors()
    total_visits = get_total_visits()

    return render_template('admin.html', system_info=system_info, current_visitors=current_visitors, total_visits=total_visits)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=10000,debug=True)
