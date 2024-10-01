import sys
import io
import subprocess
from flask import Flask, render_template, request, jsonify
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
        sys.stdin = stdin
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
    user_input = request.form.get('user_input')

    if form.validate_on_submit():
        code = form.code.data.strip()
        output = execute_python(code, user_input)

    return render_template('index.html', form=form, output=output, history=execution_history)

@app.route('/install_module', methods=['POST'])
def install_module_route():
    module = request.json.get('module')
    try:
        install_module(module)
        return jsonify({"message": f"模組 {module} 安裝成功！"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=10000, host='0.0.0.0')
