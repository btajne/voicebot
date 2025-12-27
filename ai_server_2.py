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
OLLAMA_MODEL =  "llama3.2:1b" #"llama3.1:8b"

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
    text = re.sub(r"(\d)\s*x\s*(\d)", r"\1*\2", text)
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
        return f"The answer is {result}."
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
        return "Hello! I am Aarya. How can I help you today?"

    # ---- Time & Date ----
    if re.search(r"\b(current time|time now)\b", t):
        return datetime.now().strftime("The current time is %I:%M %p.")
    if re.search(r"\b(date today|today date|what is the date)\b", t):
        return datetime.now().strftime("Today's date is %d %B %Y.")
    if re.search(r"\b(today day|what day is it)\b", t):
        return datetime.now().strftime("Today is %A.")
        
    # ---- Custom Greeting ----
    # ---- Hello Arya (specific) ----
    if re.search(r"\bhello\s+(aarya|arya|aria)\b", t):
    	return "Hello! I am Aarya. How can I help you today?"



    # ---- Identity ----
    if re.search(r"\bwho are you\b", t):
        return "I am Aarya, your friendly humanoid receptionist robot."
    if re.search(r"\byour name\b", t):
        return "My name is Aarya."

    # ---- Company ----
    # ---- Company ----
    if re.search(r"\b(ecruxbot|your company|about your company|tell me about your company)\b", t):
    	return "Ecruxbot is an Indian company creating robots and AI solutions for everyone"

	# ---- Team ----
    if re.search(r"\b(your team|tell me about your team|who is in your team)\b", t):
        return "Our team consists of Hitendra Valhe, Virendra Valhe, and Bhagyesh Tajne."

    if re.search(r"\bwebsite\b", t):
        return "You can visit our website at ecruxbot.in."
        
    if re.search(r"\blocation|address\b", t):
        return "Our office is at 2nd Floor, Near M. J. College, Jalgaon, Maharashtra, India."

    # ---- Help & Services ----
    if re.search(r"\bwhat can you do|services|help\b", t):
        return "I can answer questions, tell time, provide company info, and chat with you."

    # ---- Thank You ----
    if re.fullmatch(r"(thanks|thank you|thank u)", t):
        return "You are welcome! "

    # ---- Farewell ----
    if re.fullmatch(r"(bye|goodbye|see you)", t):
        return "Goodbye! Have a great day."

    return None


# ============================
# OLLAMA
# ============================

def ollama_reply(prompt: str) -> str:
    system_prompt = (
        "You are Aarya, a professional humanoid receptionist robot.\n"
        "Answer confidently in ONE sentence.\n"
        "Use easy and simple English.\n"
        "Do not explain reasoning.\n"
        "Never say you are an AI model.\n"
        "If you are not sure about an answer, say: "
        "'I do not have knowledge about that right now.'"
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

    # 👤 USER MESSAGE
    print("USER :", user_text, flush=True)

    if not user_text:
        reply = "Please say something."
        print("AARYA:", reply, flush=True)
        print("-" * 40)
        return jsonify({"reply": reply})

    # 1️⃣ Math
    math_reply = try_math(user_text)
    if math_reply:
        print("AARYA:", math_reply, flush=True)
        print("-" * 40)
        return jsonify({"reply": math_reply})

    # 2️⃣ Local
    reply = local_answer(user_text)
    if reply:
        print("AARYA:", reply, flush=True)
        print("-" * 40)
        return jsonify({"reply": reply})

    # 3️⃣ Ollama
    reply = ollama_reply(user_text)
    print("AARYA:", reply, flush=True)
    print("-" * 40)
    return jsonify({"reply": reply})

# ============================
# START
# ============================

if __name__ == "__main__":
    print("🤖 AARYA AI SERVER RUNNING")
    print(f"Listening on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, threaded=True)

