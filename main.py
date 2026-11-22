import os
import json
import sqlite3
from datetime import date, datetime
from dotenv import load_dotenv
from groq import Groq
import io
import wave
import numpy as np
import sounddevice as sd
import speech_recognition as sr
import re
import pyttsx3

SPEAK_REPLIES = False   # toggled by typing 'speak on' / 'speak off'

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
SAMPLE_RATE = 16000

conn = sqlite3.connect("expenses.db")
conn.execute("""CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT, amount REAL, category TEXT, note TEXT)""")

MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = (
    "You are a helpful expense tracker assistant. "
    "Always reply in English only, even if the user writes or speaks in Hindi or Hinglish. "
    "For any calculation, use the calculator tool. "
    f"Today's date is {date.today().isoformat()} (YYYY-MM-DD). "
    "Always show dates to the user in DD-MM-YYYY format. "
    "Never claim that an expense was saved, changed or deleted unless the tool result confirms it."
)

# Added to the system prompt only when the reply will be spoken aloud.
SPOKEN_STYLE = (
    "IMPORTANT: the user will HEAR this reply, not read it, so talk like a friendly person in a "
    "casual conversation. Use short, natural, flowing sentences in English. Do not use markdown, tables, bullet points, numbered lists, asterisks "
    "or emojis. Never read out every row of a list: mention only the important points, such as "
    "the total and the biggest one or two items. Keep it to 2 or 3 sentences. Write every "
    "number in words, never as digits: say 'two thousand fifty rupees' instead of '2050 rupees', "
    "'twenty' instead of '20', 'twenty-first of November' instead of '21 November' or "
    "DD-MM-YYYY (this overrides the date format rule above). "
    "After confirming something, you may add one short friendly line, but do not ramble."
)


# ---------- Tool function ----------
def calculator(expression: str) -> str:
    allowed = set("0123456789+-*/(). %")
    if not set(expression) <= allowed:
        return "Error: sirf numbers aur + - * / ( ) % allowed hain"
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception as e:
        return f"Error: {e}"

# The database always stores dates as YYYY-MM-DD (sorts and filters correctly).
# The user always sees them as DD-MM-YYYY.
def to_display(iso_date: str) -> str:
    return date.fromisoformat(iso_date).strftime("%d-%m-%Y")


def parse_date(text: str) -> str:
    """Accepts YYYY-MM-DD or DD-MM-YYYY and returns YYYY-MM-DD."""
    text = text.strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return datetime.strptime(text, "%d-%m-%Y").date().isoformat()


def add_expense(amount: str, category: str, note: str, expense_date: str = None) -> str:
    try:
        amount = float(amount)
        if expense_date:
            expense_date = parse_date(expense_date)
        else:
            expense_date = date.today().isoformat()
        conn.execute(
            "INSERT INTO expenses (date, amount, category, note) VALUES (?, ?, ?, ?)",
            (expense_date, amount, category, note),
        )
        conn.commit()
        return f"Saved: {amount} on {category} ({note}) dated {to_display(expense_date)}"
    except Exception as e:
        return f"Error: {e}"

def get_expenses(start_date: str = None, end_date: str = None, category: str = None) -> str:
    try:
        query = "SELECT id, date, amount, category, note FROM expenses WHERE 1=1"
        params = []

        if start_date:
            query += " AND date >= ?"
            params.append(parse_date(start_date))
        if end_date:
            query += " AND date <= ?"
            params.append(parse_date(end_date))
        if category:
            query += " AND LOWER(category) = LOWER(?)"
            params.append(category)

        query += " ORDER BY date DESC, id DESC"
        rows = conn.execute(query, params).fetchall()

        if not rows:
            return "No expenses found."

        expenses = [
            {"id": r[0], "date": to_display(r[1]), "amount": r[2], "category": r[3], "note": r[4]}
            for r in rows
        ]

        return json.dumps(expenses)
    except Exception as e:
        return f"Error: {e}"

def delete_expense(expense_id: str) -> str:
    try:
        expense_id = int(expense_id)

        row = conn.execute(
            "SELECT id, date, amount, category, note FROM expenses WHERE id = ?",
            (expense_id,),
        ).fetchone()

        if row is None:
            return f"Error: no expenses found with id {expense_id}"

        print(f"  [CONFIRM] Delete: id={row[0]}, {to_display(row[1])}, {row[2]}, {row[3]}, {row[4]}")
        answer = input("  Are you sure? (yes/no): ").strip().lower()

        if answer != "yes":
            return "Cancelled: the user did not give permission. Nothing was deleted."

        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
        return f"Deleted expense id {expense_id}."
    except Exception as e:
        return f"Error: {e}"

def clean_for_speech(text: str) -> str:
    """Removes markdown symbols and emojis so they are not read aloud."""
    text = re.sub(r"[*_#`|>~-]{1,}", " ", text)          # markdown symbols
    text = re.sub(r"[^\w\s.,!?₹:%/()'-]", "", text)      # emojis and other symbols
    return re.sub(r"\s+", " ", text).strip()


def speak(text: str) -> None:
    """Reads the text aloud. Never crashes the app if speech fails."""
    try:
        engine = pyttsx3.init()
        engine.say(clean_for_speech(text))
        engine.runAndWait()
    except Exception as e:
        print(f"  [SPEAK ERROR] {e}")


def speech_to_text()-> str:
    """Records the user`s voice and returns the transcribed text ('' on failure)."""
    try:
        wav_bytes = record_audio()
        if not wav_bytes:
            return ""
        recognizer = sr.Recognizer()
        with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
            audio = recognizer.record(source)
        return recognizer.recognize_google(audio, language = "en-IN")
    except sr.UnknownValueError:
        print(" [VOICE] Could not understand the audio")
        return ""
    except Exception as e:
        print(f" [VOICE ERROR] {e}")
        return ""

def record_audio()-> bytes:
    """REcords from microphone. Enter starts, Enter stops.Returns WAV bytes."""
    frames = []

    def callback(indata, frame_count, time_info, status):
        frames.append(indata.copy())

    input(" Press Enter to start recording...")
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,dtype="int16", callback=callback):
        input(" Recording... press Enter to stop.")

    if not frames:
        return b""

    audio = np.concatenate(frames)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(audio.tobytes())
    return buf.getvalue()

# ---------- Tool description (AI ke liye) ----------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Math expression calculate karta hai. Kisi bhi calculation ke liye isi ka use karo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression, jaise '250 + 130 * 2'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_expense",
            "description": "Saves a new expense. Use this when the user says they spent money on something.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "string", "description": "Amount spent e.g. '250'"},
                    "category": {"type": "string", "description": "Category such as food, travel, shopping"},
                    "note": {"type": "string", "description": "Short detail e.g. 'tea'"},
                    "expense_date": {"type": "string", "description": "Date of the expense in YYYY-MM-DD format. Only pass this if the user says it happened on a different day than today (e.g. 'yesterday', '20 Nov'). Work out the date from today's date. Omit it for today."},
                },
                "required": ["amount", "category", "note"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_expenses",
            "description": "Lists saved expenses. Optionally filter by date range and/or category. Use this when the user asks what they spent or wants to see past expenses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format (inclusive), e.g. '2026-11-06'"},
                    "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format (inclusive), e.g. '2026-11-06'"},
                    "category": {"type": "string", "description": "Category such as food, travel, shopping"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_expense",
            "description": "Deletes one expense by its id. The user will be asked to confirm. Use get_expenses first to find the correct id. Never guess an id.",
            "parameters": {
                "type": "object",
                "properties":{
                    "expense_id": { "type": "string", "description": "The id of the expense to delete, e.g. '2'"},
                },
                "required": ["expense_id"],
            }

        }
    }
]

# Tool ka naam -> asli function
AVAILABLE_FUNCTIONS = {"calculator": calculator, "add_expense": add_expense, "get_expenses": get_expenses, "delete_expense": delete_expense}


# ---------- Chat ----------
messages = [{"role": "system", "content": SYSTEM_PROMPT}]

print("Type exit to exit the Expense Tracker app.\n")

while True:
    user_input = input("You (type, or 'v' for voice): ").strip()
    used_voice = False   # becomes True only if this message was spoken

    if user_input.lower() in ("speak on", "speak off"):
        SPEAK_REPLIES = user_input.lower() == "speak on"
        print(f"  Voice replies {'ON' if SPEAK_REPLIES else 'OFF'}\n")
        continue

    if user_input.lower() == "v":
        user_input = speech_to_text()
        if not user_input:
            print(" Could not hear anything, please try again.\n")
            continue
        used_voice = True
        print(f"You (voice): {user_input}")

    if not user_input:
        continue
    if user_input.lower() in ("exit", "quit"):
        print("Bye!")
        break

    messages.append({"role": "user", "content": user_input})
    speaking = SPEAK_REPLIES or used_voice   # will this reply be read aloud?

    # ---------- Agent loop ----------
    MAX_STEPS = 5
    for step in range(MAX_STEPS):
        # For spoken replies, swap in a system prompt with the extra spoken-style rules.
        # The saved history (messages) is not changed.
        call_messages = messages
        if speaking:
            call_messages = [
                {"role": "system", "content": SYSTEM_PROMPT + " " + SPOKEN_STYLE}
            ] + messages[1:]

        resp = client.chat.completions.create(
            model=MODEL, messages=call_messages, tools=TOOLS
        )
        msg = resp.choices[0].message

        # AI ne koi tool nahi maanga -> final jawab
        if not msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content})
            print(f"AI: {msg.content}\n")
            if speaking and msg.content:
                speak(msg.content)
            break

        # AI ne tool maanga -> uska message history mein daalo
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ],
        })

        # Har tool call chalao, result history mein daalo
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
                print(f"  [TOOL] {tc.function.name}({args})")
                func = AVAILABLE_FUNCTIONS.get(tc.function.name)
                if func is None:
                    result = f"Error: unknown tool '{tc.function.name}'"
                else:
                    result = func(**args)
            except Exception as e:
                result = f"Error: {e}"
            print(f"  [RESULT] {result}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
        # loop goes back to the top, the AI now sees the tool results and replies
    else:
        print("AI: Sorry, I could not finish that request. Please try again.\n")
