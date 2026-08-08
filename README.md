# AskIvy HRMS

Final-year project: an HR management web app whose chatbot uses **Rasa CALM + Claude**
for language understanding, alongside a rule-based engine kept for comparison.

## What it does

- Employees check leave balances, apply for or cancel leave, ask policy questions,
  check parental-leave eligibility, and get career-path advice — through chat or
  the normal HRMS UI.
- Two chatbot engines run side by side and return identical response shapes:
  rule-based (`/api/askivy/chat`) and Rasa + Claude (`/api/askivy/chat-rasa`),
  switchable via `VITE_ASKIVY_ENGINE`.

```text
ChatWidget (React) → Flask API → Rasa (CALM) → Claude → action server → Flask API → DB
```

## Stack

React (Vite) · Flask + SQLAlchemy · SQLite (dev) / Postgres (prod) · Rasa Pro (CALM) + Claude

## How to run it

Four terminals, each with its own virtual environment:

```powershell
# 1. Backend — :5000
cd backend
.venv\Scripts\activate
python app.py

# 2. Rasa action server — :5055
cd rasa
.venv\Scripts\activate
rasa run actions

# 3. Rasa server — :5005
cd rasa
.venv\Scripts\activate
rasa run --enable-api --cors "*"

# 4. Frontend — :5173
cd frontend
npm install
npm run dev
```

Health check: `http://localhost:5000/api/health`
Rasa wiring check: `http://localhost:5000/api/askivy/rasa/health`

Full setup (venv creation, API keys, retraining, deployment, troubleshooting) is
documented in [`CLAUDE.md`](CLAUDE.md).
