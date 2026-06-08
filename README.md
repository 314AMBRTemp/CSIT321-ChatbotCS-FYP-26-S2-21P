# CSIT321 — AI Customer Support Chatbot
**FYP Group Project | Semester 2 | 26-S2-21P**
 
A domain-agnostic customer support chatbot targeting e-commerce and shipping, built with Google Dialogflow CX, Python Flask, and SQLite.
 
---
 
## What This System Does
 
- Embedded chat widget on a customer-facing website
- Customers can track orders, change delivery addresses, and cancel orders via natural conversation
- Dialogflow CX handles all NLP and conversation flow
- Flask backend processes webhook calls and reads/writes to the database
- Admin dashboard for managing support tickets
---
 
## Tech Stack
 
| Layer | Technology |
|---|---|
| NLP / Conversation | Google Dialogflow CX (Conversational Agents) |
| Backend | Python Flask |
| Database | SQLite via SQLAlchemy |
| Auth | Flask-Login + Flask-Bcrypt |
| Webhook Tunnel (dev) | ngrok |
| Frontend | HTML / CSS / JS |
 
---
 
## Prerequisites
 
Before you begin, make sure you have:
 
- **Python 3.10+** installed — [python.org](https://www.python.org/downloads/)
- **Git** installed — [git-scm.com](https://git-scm.com/download/win)
- **ngrok** installed — [ngrok.com/download](https://ngrok.com/download)
- A **`serviceAccountKey.json`** file — ask the project lead (this is never committed to GitHub)
- Access to the shared GCP project `csci321-chatbot-for-cs`
---
 
## Setup Instructions
 
### 1. Clone the repository
 
```bash
git clone https://github.com/314AMBRTemp/CSIT321-ChatbotCS-FYP-26-S2-21P.git
cd CSIT321-ChatbotCS-FYP-26-S2-21P
```
 
### 2. Create and activate a virtual environment
 
```bash
# Windows
python -m venv venv
venv\Scripts\activate
 
# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```
 
### 3. Install dependencies
 
```bash
pip install -r requirements.txt
```
 
### 4. Add your serviceAccountKey.json
 
Place the `serviceAccountKey.json` file in the **project root** (same folder as `app.py`).
 
> ⚠️ This file is in `.gitignore` and must NEVER be committed to GitHub. Get it from the project lead.
 
### 5. Initialise the database
 
```bash
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```
 
Or just run the app once — it auto-creates the database on first launch.
 
### 6. Start the Flask server
 
```bash
python app.py
```
 
The app runs at: **http://localhost:5000**
 
### 7. Start ngrok (for webhook)
 
Open a **second terminal** and run:
 
```bash
ngrok http 5000
```
 
Copy the `https://xxxx.ngrok-free.app` URL. You'll need to paste this into Dialogflow CX as the webhook URL.
 
### 8. Update the webhook URL in Dialogflow CX
 
1. Go to [Dialogflow CX Console](https://dialogflow.cloud.google.com/cx)
2. Select project `csci321-chatbot-for-cs`
3. Open the agent → **Manage** → **Webhooks**
4. Update the webhook URL to: `https://xxxx.ngrok-free.app/webhook`
---
 
## Project Structure
 
```
project/
├── app.py                  # Main Flask app — all routes and webhook logic
├── models.py               # SQLAlchemy models (Order, Ticket, User)
├── database.py             # DB init and seed data helpers
├── requirements.txt        # Python dependencies
├── serviceAccountKey.json  # ← NOT in Git — get from project lead
├── .gitignore
├── templates/
│   ├── base.html           # Base layout with embedded chat widget
│   ├── index.html          # Customer homepage
│   └── admin.html          # Admin dashboard
└── static/
    ├── style.css
    └── chat.js             # Chat widget logic
```
 
---
 
## Dialogflow CX Agent Details
 
| GCP Project | `csci321-chatbot-for-cs` |
| Agent ID | `e7e8fe80-878e-484e-b3d7-76ff1222b47b` |
| Location | `global` |
| Webhook endpoint | `/webhook` |
 
---
 
## Branch Structure
 
| Branch | Purpose |
|---|---|
| `main` | Stable core — backend, chatbot, database |
| `member-YHF` | Hao Feng's frontend work |
| `memeber-R` | Rommel's frontend work |
 
To work on your branch:
```bash
git checkout phil       # or roy
git pull                # get latest changes
# ... make your changes ...
git add .
git commit -m "describe your change"
git push
```
 
---
 
## Important Notes
 
- **Never commit `serviceAccountKey.json`** — it grants full GCP access
- **Never commit `.env`** — contains secrets
- The ngrok URL changes every time you restart it — update Dialogflow CX each session
- The `orders.db` SQLite file is also gitignored — each developer has their own local database
---
 
## Common Issues
 
| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` with venv activated |
| Webhook not receiving calls | Check ngrok is running and URL is updated in Dialogflow CX |
| `google.auth` errors | Check `serviceAccountKey.json` is in the project root |
| Database errors | Delete `orders.db` and re-run the app to recreate it |
| Port 5000 already in use | Run `python app.py` with `--port 5001` or kill the existing process |
 
---
 
## Contact
 
For `serviceAccountKey.json` or GCP access, contact the project lead.
