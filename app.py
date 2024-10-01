import sys
import io
import webbrowser
from flask import Flask, render_template, request, jsonify
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

# 表單類別
class CodeForm(FlaskForm):
    code = TextAreaField('輸入您的 Python 程式碼:', validators=[DataRequired()])
    submit = SubmitField('執行')

# 執行程式碼的函數
def execute_python(code):
    try:
        stdout = sys.stdout
        sys.stdout = io.StringIO()

        exec(code)
        output = sys.stdout.getvalue()

    except Exception as e:
        output = f"錯誤: {str(e)}"
    
    finally:
        sys.stdout = stdout

    return output

# 主路由
@app.route('/', methods=['GET', 'POST'])
def index():
    form = CodeForm()
    output = None
    history = []

    if form.validate_on_submit():
        code = form.code.data.strip()
        output = execute_python(code)

        # 模擬將歷史記錄保存到伺服器或瀏覽器端
        history.append((code, output))

    return render_template('index.html', form=form, output=output, history=history)

# 新增檔案的 API
@app.route('/save_file', methods=['POST'])
def save_file():
    data = request.get_json()
    filename = data.get('filename')
    content = data.get('content')
    
    # 將檔案寫入檔案系統 (模擬)
    with open(f'stored_files/{filename}', 'w') as f:
        f.write(content)

    return jsonify({"message": "檔案已儲存成功!"})

if __name__ == '__main__':
    webbrowser.open('http://localhost:22341/')
    app.run(debug=True, port=10000, host='0.0.0.0')
