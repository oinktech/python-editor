import sys
import io
import webbrowser
from flask import Flask, render_template, request
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

class CodeForm(FlaskForm):
    code = TextAreaField('Enter your Python code:', validators=[DataRequired()])
    submit = SubmitField('Run')

def execute_python(code):
    try:
        stdout = sys.stdout
        sys.stdout = io.StringIO()

        exec(code)
        output = sys.stdout.getvalue()

    except Exception as e:
        output = f"Error: {str(e)}"
    
    finally:
        sys.stdout = stdout

    return output

@app.route('/', methods=['GET', 'POST'])
def index():
    form = CodeForm()
    output = None

    if form.validate_on_submit():
        code = form.code.data.strip()
        output = execute_python(code)

    return render_template('index.html', form=form, output=output)

if __name__ == '__main__':
    webbrowser.open('http://localhost:22341/')
    app.run(debug=True, port=10000, host='0.0.0.0')
