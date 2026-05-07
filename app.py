import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
import threading, webbrowser
import utils

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "supersecretkey")

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "users.db")

# ---------- Database Setup ----------
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    cur = db.cursor()
    # users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    # predictions table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        symbol TEXT,
        input_open REAL,
        input_high REAL,
        input_low REAL,
        input_volume REAL,
        predicted_price REAL,
        created_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    db.commit()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# ---------- Routes ----------
@app.route('/')
def home():
    logged_in = session.get("user_id") is not None
    return render_template('index.html', logged_in=logged_in, username=session.get("username"))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        if not username or not password:
            return render_template('register.html', error="Please fill all fields.")
        hashed_pw = generate_password_hash(password)
        created_at = datetime.utcnow().isoformat()
        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)",
                (username, hashed_pw, created_at)
            )
            db.commit()
            flash("Account created! Please log in.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error="Username already exists.")
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        db = get_db()
        cur = db.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid username or password.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM predictions WHERE user_id = ? ORDER BY created_at DESC", (session['user_id'],))
    rows = cur.fetchall()
    return render_template('dashboard.html', rows=rows, username=session.get('username'))

@app.route('/predict', methods=['GET', 'POST'])
def predict():
    if request.method == 'POST':
        symbol = request.form.get('symbol', 'AAPL')
        try:
            Open = float(request.form.get('Open', 0))
            High = float(request.form.get('High', 0))
            Low = float(request.form.get('Low', 0))
            Volume = float(request.form.get('Volume', 0))
        except ValueError:
            return render_template('prediction.html', error="Please enter valid numeric inputs.")
        predicted = utils.preprocess(Open, High, Low, Volume)
        if session.get('user_id'):
            db = get_db()
            cur = db.cursor()
            cur.execute("""INSERT INTO predictions 
                        (user_id, symbol, input_open, input_high, input_low, input_volume, predicted_price, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""" ,
                        (session['user_id'], symbol, Open, High, Low, Volume, float(predicted), datetime.utcnow().isoformat()))
            db.commit()
        return render_template('prediction.html', predicted=predicted, symbol=symbol, username=session.get('username'))
    return render_template('prediction.html', username=session.get('username'))

@app.route('/delete_prediction/<int:pred_id>', methods=['POST'])
def delete_prediction(pred_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM predictions WHERE id = ? AND user_id = ?", (pred_id, session['user_id']))
    db.commit()
    return redirect(url_for('dashboard'))

# Keep existing chart endpoints if used by front-end JS
@app.route('/chart-data')
def chart_data():
    import yfinance as yf
    from flask import jsonify
    symbol = request.args.get('symbol', 'AAPL')
    data = yf.download(symbol, period='1mo', interval='1d')
    dates = data.index.strftime('%Y-%m-%d').tolist()
    prices = data['Close'].tolist()
    return jsonify({'dates': dates, 'prices': prices})

@app.route('/chart-data-candle')
def chart_data_candle():
    import yfinance as yf
    from flask import jsonify
    symbol = request.args.get('symbol', 'AAPL')
    data = yf.download(symbol, period='1mo', interval='1d')
    data = data.dropna()
    candles = []
    for idx, row in data.iterrows():
        candles.append({
            'x': idx.strftime('%Y-%m-%d'),
            'o': float(row['Open']),
            'h': float(row['High']),
            'l': float(row['Low']),
            'c': float(row['Close'])
        })
    return jsonify(candles)

# Auto-open browser on start
def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == '__main__':
    init_db()
    threading.Timer(1.5, open_browser).start()
    app.run(debug=True, host='0.0.0.0', port=5000)
