# Expense Tracker Agent

A terminal-based AI agent that tracks your expenses through natural conversation. You can type or speak to it, and it can read its replies aloud.

Built with Python, the [Groq](https://groq.com) API (LLM with tool calling) and SQLite. The agent loop (LLM asks for a tool, the code runs it, the result goes back to the LLM) is written by hand, without any agent framework.

## Features

- **Chat in natural language**: "I spent 20 rupees on tea today", "show my food expenses".
- **Tool calling**: the LLM decides when to call a tool, the code runs it and returns the result.
  - `add_expense`: saves an expense (amount, category, note, optional date such as "yesterday" or "20 Nov").
  - `get_expenses`: lists expenses, optionally filtered by date range and/or category.
  - `delete_expense`: deletes one expense by id, **only after you type `yes`** in the terminal.
  - `calculator`: safe math for totals and sums.
- **Voice input**: type `v`, press Enter, speak, press Enter again.
- **Voice replies**: spoken answers are written in a short, natural style, with numbers in words.
- **Local storage**: all data lives in a local SQLite file (`expenses.db`).
- **Error handling**: bad dates, bad ids, unknown tools and tool failures are reported back to the agent instead of crashing the app. The agent loop stops after 5 steps.

## Requirements

- Python 3.10+ (developed on 3.14)
- A free Groq API key: https://console.groq.com/keys
- A microphone and speakers, only if you want to use voice

## Setup

```bash
# 1. Clone and enter the project
git clone https://github.com/Rkhan76/Expense-Tracker-Agent.git
cd Expense-Tracker-Agent

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/Scripts/activate      # Git Bash on Windows
# .venv\Scripts\Activate.ps1       # PowerShell on Windows
# source .venv/bin/activate        # macOS / Linux

# 3. Install dependencies
python -m pip install -r requirements.txt

# 4. Add your API key
cp .env.example .env               # then open .env and paste your key

# 5. Run
python main.py
```

> Use `python -m pip` (not just `pip`) so packages are installed into the active virtual environment.

## Usage

At the `You (type, or 'v' for voice):` prompt:

| Input | What it does |
|---|---|
| any text | Sends your message to the agent |
| `v` | Voice input. Press Enter to start recording, Enter again to stop |
| `speak on` / `speak off` | Turn spoken replies on or off for typed messages too |
| `exit` or `quit` | Close the app |

When you speak with `v`, the reply is also spoken automatically.

Example conversation:

```
You (type, or 'v' for voice): I spent 1000 rupees on clothes yesterday
  [TOOL] add_expense({'amount': '1000', 'category': 'shopping', 'note': 'clothes', 'expense_date': '2026-11-21'})
  [RESULT] Saved: 1000.0 on shopping (clothes) dated 21-11-2026
AI: Saved. 1000 rupees on shopping for clothes, dated 21-11-2026.

You (type, or 'v' for voice): how much did I spend in total?
  [TOOL] get_expenses({})
  [TOOL] calculator({'expression': '1000 + 50'})
AI: Your total spending is 1050 rupees.
```

## How it works

```
You type or speak
      |
      v
messages list (system prompt + history + your message)
      |
      v
Groq LLM  --- no tool needed ---> final answer is printed (and spoken)
      |
  asks for a tool
      |
      v
the code runs the tool function (SQLite read or write)
      |
      v
tool result is added to messages  -->  back to the LLM (max 5 steps)
```

- **Dates** are stored as `YYYY-MM-DD` (sorts and filters correctly) and shown as `DD-MM-YYYY`. Both formats are accepted as input.
- **Delete is guarded in code**: `delete_expense` asks for confirmation with `input()` inside the function. The LLM cannot answer it, so nothing is deleted without you typing `yes`.
- **Voice input** records from the microphone with `sounddevice`, then uses the free Google speech recognizer (needs internet) through the `SpeechRecognition` package.
- **Voice replies** use `pyttsx3` (offline, uses the voices installed on your system). For spoken replies the agent gets an extra prompt asking for short, natural sentences without markdown or digits.

## Project structure

```
Expense-Tracker-Agent/
  main.py            # database, tools, voice, and the chat + agent loop
  requirements.txt   # Python dependencies
  .env.example       # template for your API key
  expenses.db        # created on first run (git-ignored)
```

## Notes and limitations

- The agent replies in English only.
- Voice input needs an internet connection and microphone permission for your terminal.
- The built-in system voices can sound robotic.
- Income is not tracked, only expenses.
- Not done yet: a `get_summary` tool (category-wise totals for a period), editing an existing expense, and automated tests.

## Tech stack

Python, Groq API (`openai/gpt-oss-120b`), SQLite, `python-dotenv`, `SpeechRecognition`, `sounddevice`, `numpy`, `pyttsx3`.
