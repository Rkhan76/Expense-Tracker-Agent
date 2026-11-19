import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = "You are a helpful expense tracker assistant. Reply in the same language as the user (Hinglish is fine). For any calculation, use the calculator tool."


# ---------- Tool function ----------
def calculator(expression: str) -> str:
    allowed = set("0123456789+-*/(). %")
    if not set(expression) <= allowed:
        return "Error: sirf numbers aur + - * / ( ) % allowed hain"
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception as e:
        return f"Error: {e}"


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
    }
]

# Tool ka naam -> asli function
AVAILABLE_FUNCTIONS = {"calculator": calculator}


# ---------- Chat ----------
messages = [{"role": "system", "content": SYSTEM_PROMPT}]

print("Type exit to exit the Expense Tracker app.\n")

while True:
    user_input = input("You: ").strip()

    if not user_input:
        continue
    if user_input.lower() in ("exit", "quit"):
        print("Bye!")
        break

    messages.append({"role": "user", "content": user_input})

    # ---------- Agent loop ----------
    while True:
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS
        )
        msg = resp.choices[0].message

        # AI ne koi tool nahi maanga -> final jawab
        if not msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content})
            print(f"AI: {msg.content}\n")
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
            args = json.loads(tc.function.arguments)
            print(f"  [TOOL] {tc.function.name}({args})")
            result = AVAILABLE_FUNCTIONS[tc.function.name](**args)
            print(f"  [RESULT] {result}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
        # loop wapas upar, AI ab result dekhkar jawab dega
