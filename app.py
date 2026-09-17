from flask import Flask, render_template, request, redirect, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import random
import os
from textblob import TextBlob
import pickle
import json
# Load trained AI model
model = pickle.load(open("model.pkl", "rb"))
vectorizer = pickle.load(open("vectorizer.pkl", "rb"))

# Load dataset
with open("dataset/intents.json") as file:
    intents = json.load(file)
def get_ai_response(text):

    X = vectorizer.transform([text])
    tag = model.predict(X)[0]

    for intent in intents["intents"]:
        if intent["tag"] == tag:
            return random.choice(intent["responses"]), tag

    return "I'm here to listen.", "neutral"

from emotion_model import detect_emotion
from crisis_detection import detect_crisis
from mood_history import save_mood

app = Flask(__name__)
app.secret_key = "mentalhealth"


# -----------------------------
# DATABASE INITIALIZATION
# -----------------------------
def init_db():

    conn = sqlite3.connect("mental_health.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    password TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mood_history(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    message TEXT,
    emotion TEXT,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


init_db()

def save_mood(username,message,emotion):

    conn=sqlite3.connect("mental_health.db")
    cursor=conn.cursor()

    cursor.execute(
    "INSERT INTO mood_history(username,message,emotion) VALUES(?,?,?)",
    (username,message,emotion)
    )

    conn.commit()
    conn.close()
# -----------------------------
# MOOD DETECTION
# -----------------------------
def detect_mood(text):

    polarity = TextBlob(text).sentiment.polarity

    if polarity > 0:
        return "Happy"
    elif polarity < 0:
        return "Sad"
    else:
        return "Neutral"
# -----------------------------
# ADMIN PAGE
# -----------------------------
@app.route("/admin")
def admin():

    if session.get("user") != "admin":
        return "Access Denied ❌"

    conn = sqlite3.connect("mental_health.db")
    cursor = conn.cursor()

    cursor.execute("SELECT username FROM users")
    users = cursor.fetchall()

    cursor.execute("SELECT username, emotion, date FROM mood_history ORDER BY date DESC")
    moods = cursor.fetchall()

    conn.close()

    return render_template("admin.html", users=users, moods=moods)
# -----------------------------
# CREATING ADMIN
# -----------------------------
@app.route("/create_admin")
def create_admin():

    conn = sqlite3.connect("mental_health.db")
    cursor = conn.cursor()

    hashed = generate_password_hash("admin123")

    cursor.execute(
        "INSERT INTO users(username,password) VALUES(?,?)",
        ("admin", hashed)
    )

    conn.commit()
    conn.close()

    return "Admin created"
# -----------------------------
# LOGIN PAGE
# -----------------------------
@app.route("/")
def home():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login_user():

    user = request.form.get("user")
    password = request.form.get("password")

    conn = sqlite3.connect("mental_health.db")
    cur = conn.cursor()

    cur.execute("SELECT password FROM users WHERE username=?", (user,))
    data = cur.fetchone()

    conn.close()

    if data and check_password_hash(data[0], password):
        session["user"] = user
        return redirect("/dashboard")
    else:
        return render_template("login.html", error="Invalid username or password")

# -----------------------------
# REGISTER
# -----------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        user = request.form["user"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect("mental_health.db")
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO users(username,password) VALUES(?,?)",
            (user, hashed_password)
        )

        conn.commit()
        conn.close()

        session["user"] = user

        return redirect("/chat")

    return render_template("register.html")

# -----------------------------
# DASHBOARD (MOOD ANALYTICS)
# -----------------------------
@app.route("/dashboard")
def dashboard():

    conn = sqlite3.connect("mental_health.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT emotion, COUNT(*) FROM mood_history GROUP BY emotion"
    )

    data = cursor.fetchall()

    conn.close()

    moods = [row[0] for row in data]
    counts = [row[1] for row in data]

    return render_template(
        "dashboard.html",
        moods=moods,
        counts=counts
    )


# -----------------------------
# MOOD ANALYTICS PAGE
# -----------------------------
@app.route("/mood_analytics")
def mood_analytics():

    conn = sqlite3.connect("mental_health.db")
    cursor = conn.cursor()

    cursor.execute("SELECT emotion, COUNT(*) FROM mood_history GROUP BY emotion")

    data = cursor.fetchall()

    conn.close()

    moods = [row[0] for row in data]
    counts = [row[1] for row in data]

    return render_template("mood_analytics.html", moods=moods, counts=counts)


# -----------------------------
# CHAT PAGE
# -----------------------------
@app.route("/chat")
def chat():
    return render_template("chat.html")


# -----------------------------
# CHATBOT RESPONSE
# -----------------------------
@app.route("/get_response", methods=["POST"])
def response():

    data = request.get_json()
    user_text = data.get("message", "").lower()

    # AI response
    reply, emotion = get_ai_response(user_text)

    # Save mood
    save_mood(session.get("user", "guest"), user_text, emotion)

    # Crisis detection override
    if detect_crisis(user_text):
        reply = (
            "I'm really sorry you're feeling this way.\n\n"
            "Please contact a mental health helpline immediately.\n"
            "📞 915298721"
        )

    return jsonify({
        "reply": reply,
        "emotion": emotion
    })

@app.route("/view_users")
def view_users():

    conn = sqlite3.connect("mental_health.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users")
    data = cursor.fetchall()

    conn.close()

    return str(data)
# -----------------------------
# RUN APP
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5001)
