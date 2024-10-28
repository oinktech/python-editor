from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
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
from concurrent.futures import ProcessPoolExecutor

# 加載環境變數
load_dotenv()

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# 表單類，用於輸入 Python 程式碼
class CodeForm(FlaskForm):
    code = TextAreaField('輸入您的 Python 程式碼：', validators=[DataRequired()])
    submit = SubmitField('執行')

# 存儲執行歷史
execution_history = []

# 連接 SQLite 資料庫
def get_db_connection():
    conn = sqlite3.connect('visitors.db')
    conn.row_factory = sqlite3.Row
    return conn

# 初始化資料庫
def init_db():
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS visitors (
                user_id TEXT PRIMARY KEY,
                last_seen INTEGER,
                ip_address TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS total_visits (
                visit_count INTEGER
            )
        ''')
        # 初始化總訪問人數
        if conn.execute('SELECT COUNT(*) FROM total_visits').fetchone()[0] == 0:
            conn.execute('INSERT INTO total_visits (visit_count) VALUES (0)')

# 执行 Python 程式碼的函数
def execute_python(code, user_input=None):
    output = ""
    try:
        # 重定向標準輸出與輸入
        stdout = sys.stdout
        sys.stdout = io.StringIO()

        if user_input:
            sys.stdin = io.StringIO(user_input)

        # 特殊命令處理
        if code.startswith('!pip install'):
            module = code.split(' ')[-1]
            install_module(module)
            output = f"模塊 {module} 安裝成功！"
        elif code.startswith('!pip uninstall'):
            output = "⚠️由於安全性及相關考量，因此已移除該功能。⚠️"
        elif code.startswith('!pip install --upgrade'):
            module = code.split(' ')[-1]
            update_module(module)
            output = f"模塊 {module} 更新成功！"
        elif code.startswith('!pip list'):
            output = list_installed_modules()
        elif code.startswith('!'):
            output = "⚠️ 此命令不允許執行。⚠️"
        else:
            exec(code)
            output = sys.stdout.getvalue()

    except Exception as e:
        output = f"錯誤：{str(e)}"
    
    finally:
        sys.stdout = stdout
        output = escape(output)
        execution_history.append((code, output))
    
    return output

# 安裝 Python 模塊
def install_module(module):
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", module], check=True)
    except subprocess.CalledProcessError as e:
        raise Exception(f"模塊安裝失敗：{e}")

# 更新 Python 模塊
def update_module(module):
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", module], check=True)
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
def get_system_info():
    total, used, free = shutil.disk_usage("/")
    disk_usage = {
        "total": total // (2**30),
        "used": used // (2**30),
        "free": free // (2**30)
    }

    cpu_usage = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    memory_usage = {
        "total": memory.total // (2**30),
        "used": memory.used // (2**30),
        "free": memory.available // (2**30)
    }

    return {
        "disk_usage": disk_usage,
        "cpu_usage": cpu_usage,
        "memory_usage": memory_usage
    }

# 追蹤訪客資料
def track_visitor(ip_address):
    with get_db_connection() as conn:
        if 'user_id' not in session:
            session['user_id'] = str(time.time())

        user_id = session['user_id']
        current_time = int(time.time())

        conn.execute('INSERT OR REPLACE INTO visitors (user_id, last_seen, ip_address) VALUES (?, ?, ?)', (user_id, current_time, ip_address))
        conn.execute('DELETE FROM visitors WHERE last_seen < ?', (current_time - 300,))
        conn.execute('UPDATE total_visits SET visit_count = visit_count + 1')

# 查看當前在線人數
def get_current_visitors():
    with get_db_connection() as conn:
        return conn.execute('SELECT COUNT(*) FROM visitors').fetchone()[0]

# 查看歷史總訪問人數
def get_total_visits():
    with get_db_connection() as conn:
        return conn.execute('SELECT visit_count FROM total_visits').fetchone()[0]

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
    ip_address = request.remote_addr
    track_visitor(ip_address)

    if form.validate_on_submit():
        code = form.code.data
        with ProcessPoolExecutor() as executor:
            output = executor.submit(execute_python, code).result()

    return render_template('index.html', form=form, output=output, history=execution_history)

# 處理 AJAX 請求以執行 Python 程式碼
@app.route('/execute', methods=['POST'])
def execute_code():
    code = request.form['code']
    with ProcessPoolExecutor() as executor:
        output = executor.submit(execute_python, code).result()
    return jsonify({'output': output})

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(Exception)
def handle_error(e):
    error_message = str(e)
    return render_template('error.html', error_message=error_message), 500

# 管理頁面路由
@app.route('/admin')
def admin():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    ip_address = request.remote_addr
    system_info = get_system_info()
    current_visitors = get_current_visitors()
    total_visits = get_total_visits()
    return render_template('admin.html', system_info=system_info, current_visitors=current_visitors, total_visits=total_visits, ip_address=ip_address)

# 提供 JSON 格式的系統信息和網站流量數據
@app.route('/system_info')
def system_info():
    info = get_system_info()
    info['current_visitors'] = get_current_visitors()
    info['total_visits'] = get_total_visits()
    return jsonify(info)

if __name__ == '__main__':
    init_db()  # 初始化資料庫
    app.run(port=10000, host='0.0.0.0', debug=True)
