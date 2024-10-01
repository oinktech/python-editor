import sys
import io
import subprocess
import time
from flask import Flask, render_template, request, jsonify
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

class CodeForm(FlaskForm):
    code = TextAreaField('輸入您的 Python 程式碼：', validators=[DataRequired()])
    submit = SubmitField('執行')

def install_module(module):
    process = subprocess.Popen(
        [sys.executable, '-m', 'pip', 'install', module],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            yield output.strip()
            time.sleep(1)  # 模擬進度延遲

@app.route('/', methods=['GET', 'POST'])
def index():
    form = CodeForm()
    output = None

    if form.validate_on_submit():
        code = form.code.data
        if code.startswith('!pip install'):
            module = code.split(' ')[-1]
            progress_message = '正在安裝模組...'
            return jsonify({'progress': 100, 'message': progress_message})

        # Execute the code
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            exec(code)
            output = sys.stdout.getvalue()
        except Exception as e:
            output = f'錯誤: {str(e)}'
        finally:
            sys.stdout = old_stdout

    return render_template('index.html', form=form, output=output)

if __name__ == '__main__':
    app.run(debug=True)
