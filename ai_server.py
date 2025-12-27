#!/usr/bin/env python3

from flask import Flask, request, jsonify
from datetime import datetime
import ollama
import re
import ast
import operator

# ============================
# CONFIG
# ============================
HOST = "0.0.0.0"
PORT = 8000
OLLAMA_MODEL = "llama3.1:8b"

app = Flask(__name__)

# ============================
# SAFE MATH ENGINE
# ============================

NUM_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12
}

OP_WORDS = {
    "plus": "+",
    "minus": "-",
    "into": "*",
    "times": "*",
    "multiplied by": "*",
    "divide by": "/",
    "divided by": "/"
}

ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv
}

def words_to_numbers(text: str) -> str:
    for word, num in NUM_WORDS.items():
        text = re.sub(rf"\b{word}\b", str(num), text)
    return text

def words_to_operators(text: str) -> str:
    text = re.sub(r"(\d)\s*x\s*(\d)", r"\1*\2", text)  # ✅ ADD THIS
    for word, op in OP_WORDS.items():
        text = text.replace(word, op)
    return text


def safe_eval(expr: str):
    def _eval(node):
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.BinOp):
            if type(node.op) not in ALLOWED_OPS:
                raise ValueError("Invalid operator")
            return ALLOWED_OPS[type(node.op)](
                _eval(node.left), _eval(node.right)
            )
        raise ValueError("Invalid expression")

    tree = ast.parse(expr, mode="eval")
    return _eval(tree.body)

def try_math(text: str):
    t = text.lower()

    if not re.search(r"(plus|minus|into|times|multiply|multiplied|divide|divided|\d|x)", t):
        return None

    t = words_to_numbers(t)
    t = words_to_operators(t)
    t = re.sub(r"[^\d+\-*/. ]", "", t).strip()

    try:
        result = safe_eval(t)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return f"The answer is: {result}."
    except Exception:
        return None

# ============================
# TEXT NORMALIZER
# ============================
def normalize_intent(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    return text

# ============================
# FAST LOCAL ANSWERS
# ============================
def local_answer(text: str):
    t = normalize_intent(text)

    # ---- Greetings ----
    if re.fullmatch(r"(hi|hello|hey|namaste)( aarya| ariya)?", t):
        return "Hello, I am Aarya, how can I assist you today."
        
    if re.fullmatch(r"hello arya", t):
    	return "Hello, I am Aarya, how can I assist you today."

    # ---- Time & Date ----
    if re.search(r"\b(current time|time now)\b", t):
        return datetime.now().strftime("The current time is %I:%M %p.")
    if re.search(r"\b(date today|today date)\b", t):
        return datetime.now().strftime("Today's date is %d %B %Y.")
    if re.search(r"\b(today day|what day)\b", t):
        return datetime.now().strftime("Today is %A.")
    if re.search(r"\b(current month)\b", t):
        return datetime.now().strftime("The current month is %B.")
    if re.search(r"\b(current year)\b", t):
        return datetime.now().strftime("The current year is %Y.")

    # ---- Identity ----
    if re.search(r"\bwho are you\b", t):
        return "I am Aarya, a humanoid receptionist robot developed by Ecruxbot."
    if re.search(r"\byour name\b", t):
        return "My name is Aarya."
    if re.search(r"\bhow are you\b", t):
        return "I am fine, thank you for asking."

    if re.search(r"\bfeatures\b", t):
        return "I can communicate through speech, answer visitor queries, and showcase company technologies."

    # ---- Company ----
    
    if re.search(r"\becruxbot\b", t):
        return "Ecruxbot is an Indian robotics and artificial intelligence company."
    if re.search(r"\b(tell me about your company|about your company|your company)\b", t):
    	return "Ecruxbot is an Indian robotics and artificial intelligence company."

    if re.search(r"\bteam\b", t):
        return "The Ecruxbot team includes Hitendra Valhe, Bhagyesh Tajne, and Virendra Valhe."
    if re.search(r"\bwebsite\b", t):
        return "Our official website is ecruxbot.in."
    if re.search(r"\b(contact|email)\b", t):
        return "You can contact Ecruxbot at ecruxbot@gmail.com."
    if re.search(r"\bpurpose\b|\bwhy are you here\b", t):
        return "I am designed to assist visitors and provide information."
    if re.search(r"\blanguage\b", t):
        return "I currently speak English and will support Hindi and Marathi in the future."

    # ---- Thank you (ONLY if standalone) ----
    if re.fullmatch(r"(thanks|thank you|thank u)", t):
        return "You are welcome."

    return None
# ============================
# OLLAMA
# ============================
def ollama_reply(prompt: str) -> str:
    system_prompt = (
    "You are Aarya, a friendly humanoid receptionist created by Ecruxbot.\n"
    "Speak like a calm, helpful human using simple, natural English.\n"
    "Always reply in ONE short sentence, under 40 words.\n"
    "Be confident but polite.\n"
    "Do not explain steps or reasoning.\n"
    "If you are unsure or the information may be incorrect, say exactly:\n"
    "'I don’t have information about that right now.'\n"
    "Never guess or assume facts.\n"
    "Never mention being an AI, model, or chatbot.\n"
    "Do not roleplay as a hotel or service desk."
    )

    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    )

    return response["message"]["content"].strip()

# ============================
# API
# ============================

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    user_text = data.get("text", "").strip()

    if not user_text:
        reply = "Please say something."
        print("USER :", user_text)
        print("AARYA:", reply)
        print("-" * 40)
        return jsonify({"reply": reply})

    # 1️⃣ Math FIRST
    math_reply = try_math(user_text)
    if math_reply:
        print("USER :", user_text)
        print("AARYA:", math_reply)
        print("-" * 40)
        return jsonify({"reply": math_reply})

    # 2️⃣ Local answers
    reply = local_answer(user_text)
    if reply:
        print("USER :", user_text)
        print("AARYA:", reply)
        print("-" * 40)
        return jsonify({"reply": reply})

    # 3️⃣ Ollama
    reply = ollama_reply(user_text)
    print("USER :", user_text)
    print("AARYA:", reply)
    print("-" * 40)
    return jsonify({"reply": reply})


# ============================
# START
# ============================
if __name__ == "__main__":
    print("🤖 AARYA AI SERVER RUNNING")
    print(f"Listening on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, threaded=True)

