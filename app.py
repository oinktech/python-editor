from flask import Flask, render_template, request, jsonify, session
import redis
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

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# 配置 Redis 連接
r = redis.StrictRedis(host='localhost', port=6379, db=0)

# 設定 session 過期時間，假設以秒為單位
SESSION_TIMEOUT = 300

# 表單類別，用於輸入 Python 程式碼
class CodeForm(FlaskForm):
    code = TextAreaField('輸入您的 Python 程式碼：', validators=[DataRequired()])
    submit = SubmitField('執行')

# 儲存執行歷史
execution_history = []

# 執行 Python 程式碼的函數
def execute_python(code, user_input=None):
    global execution_history
    output = ""
    try:
        # 重定向標準輸出與輸入
        stdout = sys.stdout
        stdin = sys.stdin
        sys.stdout = io.StringIO()

        if user_input:
            sys.stdin = io.StringIO(user_input)

        # 特殊命令處理
        if code.startswith('!pip install'):
            module = code.split(' ')[-1]
            install_module(module)
            output = f"模組 {module} 安裝成功！"
        elif code.startswith('!pip uninstall'):
            output = f"⚠️由於安全性及相關考量，因此已移除該功能。⚠️"
        elif code.startswith('!pip install --upgrade'):
            module = code.split(' ')[-1]
            update_module(module)
            output = f"模組 {module} 更新成功！"
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
        sys.stdin = stdin
        output = escape(output)
        execution_history.append((code, output))

    return output

# 安裝 Python 模組
def install_module(module):
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", module], check=True, timeout=60)
    except subprocess.CalledProcessError as e:
        raise Exception(f"模組安裝失敗：{e}")

# 更新 Python 模組
def update_module(module):
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", module], check=True, timeout=60)
    except subprocess.CalledProcessError as e:
        raise Exception(f"模組更新失敗：{e}")

# 列出已安裝的模組
def list_installed_modules():
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"模組列出失敗：{e}"

# 獲取系統資源使用情況
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

    return {
        "disk_usage": disk_usage,
        "cpu_usage": cpu_usage,
        "memory_usage": memory_usage
    }

# 追蹤訪問者數據
def track_visitor():
    # 如果 session 沒有 'user_id'，則生成一個唯一 ID
    if 'user_id' not in session:
        session['user_id'] = time.time()

    user_id = session['user_id']
    current_time = int(time.time())

    # 在 Redis 中記錄這位訪問者
    r.hset('visitors', user_id, current_time)

    # 清理已過期的訪問者
    for visitor, last_seen in r.hgetall('visitors').items():
        if current_time - int(last_seen) > SESSION_TIMEOUT:
            r.hdel('visitors', visitor)

    # 增加歷史訪問人數
    r.incr('total_visits')

# 查看目前在線人數
def get_current_visitors():
    return r.hlen('visitors')

# 查看歷史總訪問人數
def get_total_visits():
    return int(r.get('total_visits') or 0)

# 主頁路由，處理 Python 程式碼執行
@app.route('/', methods=['GET', 'POST'])
def index():
    form = CodeForm()
    output = None

    if form.validate_on_submit():
        code = form.code.data
        user_input = request.form.get('user_input')
        output = execute_python(code, user_input)

    return render_template('index.html', form=form, output=output, history=execution_history)

# 管理頁面路由，顯示系統資源使用情況和網站流量信息
@app.route('/admin')
def admin():
    system_info = get_system_info()
    current_visitors = get_current_visitors()
    total_visits = get_total_visits()
    return render_template('admin.html', system_info=system_info, current_visitors=current_visitors, total_visits=total_visits)

# 提供 JSON 格式的系統資訊和網站流量數據
@app.route('/system_info')
def system_info():
    info = get_system_info()
    info['current_visitors'] = get_current_visitors()
    info['total_visits'] = get_total_visits()
    return jsonify(info)

if __name__ == '__main__':
    app.run(debug=True, port=10000, host='0.0.0.0')
