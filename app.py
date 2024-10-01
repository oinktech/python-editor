import sys
import io
import subprocess
from flask import Flask, render_template, request
from markupsafe import escape  # 匯入 escape 函數
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

class CodeForm(FlaskForm):
    code = TextAreaField('輸入您的 Python 程式碼：', validators=[DataRequired()])
    submit = SubmitField('執行')

execution_history = []

def execute_python(code, user_input=None):
    global execution_history
    output = ""
    try:
        stdout = sys.stdout
        stdin = sys.stdin
        sys.stdout = io.StringIO()

        if user_input:
            sys.stdin = io.StringIO(user_input)

        # Handle specific pip commands safely
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

        # For other unknown "!" commands, restrict them and return error
        elif code.startswith('!'):
            output = "⚠️ 此命令不允許執行。⚠️"

        else:
            # Execute Python code
            exec(code)
            output = sys.stdout.getvalue()

    except Exception as e:
        output = f"錯誤：{str(e)}"
    
    finally:
        sys.stdout = stdout
        sys.stdin = stdin
        # Escape output to prevent XSS
        output = escape(output)
        execution_history.append((code, output))

    return output

def install_module(module):
    """安全地安裝 Python 模組"""
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", module], check=True, timeout=60)
    except subprocess.CalledProcessError as e:
        raise Exception(f"模組安裝失敗：{e}")

def update_module(module):
    """安全地更新 Python 模組"""
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", module], check=True, timeout=60)
    except subprocess.CalledProcessError as e:
        raise Exception(f"模組更新失敗：{e}")

def list_installed_modules():
    """列出已安裝的 Python 模組"""
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"模組列出失敗：{e}"

@app.route('/', methods=['GET', 'POST'])
def index():
    form = CodeForm()
    output = None

    if form.validate_on_submit():
        code = form.code.data
        user_input = request.form.get('user_input')
        output = execute_python(code, user_input)

    return render_template('index.html', form=form, output=output, history=execution_history)

if __name__ == '__main__':
    app.run(debug=True, port=10000, host='0.0.0.0')
