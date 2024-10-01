import sys
import io
import subprocess
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

def execute_python(code):
    global execution_history
    output = ""
    try:
        stdout = sys.stdout
        sys.stdout = io.StringIO()

        if code.startswith('!pip install'):
            module = code.split(' ')[-1]
            install_module(module)
            output = f"模組 {module} 安裝成功！"
        else:
            exec(code)
            output = sys.stdout.getvalue()
            
    except Exception as e:
        output = f"錯誤：{str(e)}"
    
    finally:
        sys.stdout = stdout
        execution_history.append((code, output))

    return output

def install_module(module):
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", module], check=True)
    except subprocess.CalledProcessError as e:
        raise Exception(f"模組安裝失敗：{e}")

@app.route('/', methods=['GET', 'POST'])
def index():
    form = CodeForm()
    output = None

    if form.validate_on_submit():
        code = form.code.data.strip()
        output = execute_python(code)

    return render_template('index.html', form=form, output=output, history=execution_history)

if __name__ == '__main__':
    app.run(debug=True, port=10000, host='0.0.0.0')
