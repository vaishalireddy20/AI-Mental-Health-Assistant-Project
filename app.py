from flask import Flask, render_template, request, redirect, session, jsonify
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
# LOGIN PAGE
# -----------------------------
@app.route("/")
def login():
    return render_template("login.html")


# -----------------------------
# REGISTER
# -----------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        user = request.form["user"]
        password = request.form["password"]

        conn = sqlite3.connect("mental_health.db")
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO users(username,password) VALUES(?,?)",
            (user, password)
        )

        conn.commit()
        conn.close()

        # store user in session
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
# -----------------------------
# RUN APP
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
