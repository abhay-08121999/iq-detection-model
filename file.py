import random
import json
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key'

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
USERS_FILE = 'users.json'

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def generate_question(existing_questions):
    prompt = """
    Generate a unique quantitative aptitude multiple-choice question in JSON format like:
    {
      "question": "Your question here",
      "options": ["A", "B", "C", "D"],
      "correct_answer": "A"
    }
    Make sure the question is not repeated.
    """
    model = genai.GenerativeModel('gemini-2.0-flash-001')
    for _ in range(5):
        response = model.generate_content(prompt)
        text = response.text.strip()
        start = text.find('{')
        end = text.rfind('}') + 1
        try:
            question_data = json.loads(text[start:end])
            if question_data["question"] not in [q["question"] for q in existing_questions]:
                return question_data
        except:
            continue
    return None

@app.route('/')
def home():
    return render_template('01_index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()

        users = load_users()
        errors = {}

        if not username:
            errors['username'] = 'Username is required.'
        elif username in users:
            errors['username'] = 'Username already exists.'

        if not email:
            errors['email'] = 'Email is required.'
        elif any(user['email'] == email for user in users.values()):
            errors['email'] = 'Email already registered.'

        if not password:
            errors['password'] = 'Password is required.'

        if errors:
            return jsonify(success=False, errors=errors)

        users[username] = {
            'email': email,
            'password': password
        }
        save_users(users)
        return jsonify(success=True)

    return render_template('02_register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            username = request.form['username']
            password = request.form['password']
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            age = request.form['age']
            education = request.form['education']
            phone = request.form['phone']

            if not phone.isdigit() or len(phone) != 10:
                flash("Phone number must be exactly 10 digits.", "error")
                return redirect(url_for('login'))

            users = load_users()
            if username in users and users[username]['password'] == password:
                users[username].update({
                    'first_name': first_name,
                    'last_name': last_name,
                    'age': age,
                    'education': education,
                    'phone': phone
                })
                save_users(users)

                session['user'] = username
                session['first_name'] = first_name
                session['last_name'] = last_name
                session['age'] = age
                session['education'] = education
                session['phone'] = phone

                flash("Login successful!", "success")
                return redirect(url_for('quiz'))
            else:
                flash("Invalid username or password.", "error")
        except KeyError:
            flash("Please fill all fields correctly.", "error")
        return redirect(url_for('login'))

    return render_template('03_login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))

@app.route('/quiz')
def quiz():
    if 'user' not in session:
        flash("Please log in to take the quiz.", "warning")
        return redirect(url_for('login'))

    if 'questions' not in session or 'current' not in session:
        session['questions'] = []
        while len(session['questions']) < 20:
            q = generate_question(session['questions'])
            if q:
                session['questions'].append(q)

        session['current'] = 0
        session['answers'] = {}
        session['status'] = ['Not Attempted'] * len(session['questions'])

    index = session['current']
    selected = session['answers'].get(str(index), None)

    return render_template('04_quiz.html',
        question=session['questions'][index],
        index=index,
        total=len(session['questions']),
        status=session['status'],
        selected=selected
    )

@app.route('/next', methods=['POST'])
def next_question():
    index = session['current']
    answer = request.form.get('answer')

    if answer:
        session['answers'][str(index)] = answer
        session['status'][index] = 'Attempted'

    if index + 1 < len(session['questions']):
        session['current'] += 1

    return redirect(url_for('quiz'))

@app.route('/prev', methods=['POST'])
def prev_question():
    index = session['current']
    answer = request.form.get('answer')

    if answer:
        session['answers'][str(index)] = answer
        session['status'][index] = 'Attempted'

    if index > 0:
        session['current'] -= 1

    return redirect(url_for('quiz'))

@app.route('/submit', methods=['POST'])
def submit():
    index = session['current']
    answer = request.form.get('answer')

    if answer:
        session['answers'][str(index)] = answer
        session['status'][index] = 'Attempted'

    score = 0
    for i, q in enumerate(session['questions']):
        if session['answers'].get(str(i)) == q['correct_answer']:
            score += 1

    total = len(session['questions'])
    percent = (score / total) * 100
    if percent >= 90:
        iq = "Genius (IQ > 140)"
    elif percent >= 75:
        iq = "Above Average (IQ 120–140)"
    elif percent >= 50:
        iq = "Average (IQ 90–120)"
    else:
        iq = "Below Average (IQ < 90)"

    return render_template("05_result.html", score=score, total=total, iq_range=iq)

@app.route('/retry')
def retry():
    session.pop('questions', None)
    session.pop('answers', None)
    session.pop('status', None)
    session.pop('current', None)
    flash("New quiz started!", "info")
    return redirect(url_for('quiz'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)
