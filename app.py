import sys
import io
import subprocess
import time
from flask import Flask, render_template, request, jsonify
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

class CodeForm(FlaskForm):
    code = TextAreaField('輸入您的 Python 程式碼：', validators=[DataRequired()])
    submit = SubmitField('執行')

execution_history = []

def execute_python(code, user_input=None):
    global execution_history
    output = ""
    stdout = sys.stdout
    stdin = sys.stdin
    sys.stdout = io.StringIO()
    
    try:
        if user_input:
            sys.stdin = io.StringIO(user_input)

        if code.startswith('!pip install'):
            module = code.split(' ')[-1]
            output = install_module(module)
        else:
            exec(code, globals())
            output = sys.stdout.getvalue()

    except Exception as e:
        output = f"錯誤：{str(e)}"
    finally:
        sys.stdout = stdout
        sys.stdin = stdin

    execution_history.append((code, output))
    return output

def install_module(module):
    try:
        # 模擬下載進度
        for i in range(5):
            time.sleep(1)  # 模擬下載過程
        subprocess.run([sys.executable, "-m", "pip", "install", module], check=True)
        return f"模組 {module} 安裝成功！"
    except subprocess.CalledProcessError as e:
        return f"模組安裝失敗：{str(e)}"

@app.route('/', methods=['GET', 'POST'])
def index():
    form = CodeForm()
    output = None
    page = request.args.get('page', 1, type=int)
    items_per_page = 5
    total_pages = (len(execution_history) + items_per_page - 1) // items_per_page
    start = (page - 1) * items_per_page
    end = start + items_per_page
    paginated_history = execution_history[start:end]
    
    if form.validate_on_submit():
        code = form.code.data
        output = execute_python(code)
        return render_template('index.html', form=form, output=output, paginated_history=paginated_history, current_page=page, total_pages=total_pages, items_per_page=items_per_page)

    return render_template('index.html', form=form, paginated_history=paginated_history, current_page=page, total_pages=total_pages, items_per_page=items_per_page)

@app.route('/install_module', methods=['POST'])
def install_module_route():
    module = request.json.get('module')
    try:
        result = install_module(module)
        return jsonify({"message": result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=10000, host='0.0.0.0', debug=True)
