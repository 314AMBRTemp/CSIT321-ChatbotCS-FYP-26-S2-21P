# AssistFlow — AI Customer Support Chatbot

**CSIT321 Final Year Project | Group 26 | Semester 2 2026**

An e-commerce storefront with an embedded AI chatbot powered by Google Dialogflow CX. Customers can track orders, change delivery addresses, cancel orders, and raise support tickets through natural conversation. Admins manage tickets and chatbot responses through a dashboard.

---

## Tech Stack

| Layer | Technology |
|---|---|
| NLP / Conversation | Google Dialogflow CX (asia-southeast1) |
| Backend | Python Flask 3.1.3 |
| Database | SQLite via SQLAlchemy |
| Auth | Flask-Login + Flask-Bcrypt |
| Fuzzy FAQ Match | fuzzywuzzy + python-Levenshtein |
| Webhook Tunnel (dev) | ngrok |
| Frontend | Bootstrap 4, jQuery, Themify Icons |

---

## Prerequisites

- **Python 3.10+** — [python.org/downloads](https://www.python.org/downloads/)
- **Git** — [git-scm.com](https://git-scm.com/download/win)
- **ngrok** — [ngrok.com/download](https://ngrok.com/download) (place `ngrok.exe` in project root)
- **`serviceAccountKey.json`** — ask the project lead (never committed to GitHub)
- Access to GCP project `csci321-chatbot-for-cs`

---

## Setup

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

# Mac / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Place secret files in the project root

| File | Purpose |
|---|---|
| `serviceAccountKey.json` | Google Cloud credentials for Dialogflow CX |
| `ngrok.exe` | Webhook tunnel binary |

> Both files are in `.gitignore` and must never be committed.

### 5. Seed the database

Run once after a fresh clone (safe to re-run — scripts are idempotent):

```bash
python seed.py        # 5 customers + 8 orders
python seed_admin.py  # admin account
python seed_more.py   # 4 more customers + 17 orders + 10 tickets
```

### 6. Start the Flask app

```bash
python app.py
```

App runs at: **http://localhost:5000**

### 7. Start ngrok (for Dialogflow webhook)

Open a second terminal in the project root:

```bash
./ngrok.exe http 5000
```

Copy the `https://xxxx.ngrok-free.app` URL.

### 8. Update the webhook URL in Dialogflow CX

1. Open [Dialogflow CX Console](https://conversational-agents.cloud.google.com/)
2. Select project `csci321-chatbot-for-cs` → agent `e7e8fe80-878e-484e-b3d7-76ff1222b47b`
3. Go to **Manage** → **Webhooks** → `verify_and_fetch_order`
4. Set URL to: `https://xxxx.ngrok-free.app/webhook`

> The ngrok URL changes on every restart — repeat this step each session.

---

## Check Services

Run `check_services.bat` (double-click or from terminal) to verify Flask and ngrok are running and print the live public URL.

---

## Test Accounts

All customer passwords: `password123` | Admin password: `admin123`

| Role | Email | Orders |
|---|---|---|
| Admin | admin@shopbot.com | — |
| Alice Tan | alice@email.com | 4 |
| Bob Lim | bob@email.com | 4 |
| Carol Ng | carol@email.com | 2 |
| David Koh | david@email.com | 2 |
| Emily Lim | emily@email.com | 3 |
| Fiona Yap | fiona@email.com | 3 |
| George Tan | george@email.com | 2 |
| Hannah Wong | hannah@email.com | 3 |
| Ivan Chua | ivan@email.com | 2 |

Login pages: `/customer/login` (customers) · `/admin/login` (admin)

---

## Project Structure

```
app.py                        # Flask app factory, blueprint registration, product routes
extensions.py                 # db, bcrypt, login_manager singletons
models.py                     # Admin, Customer, Order, Ticket, BotResponse
requirements.txt
routes/
  admin.py                    # /admin/* — dashboard, tickets, response CMS
  customer_auth.py            # /customer/login|register|dashboard|logout
  webhook.py                  # /chat (Dialogflow) + /webhook (fulfillment)
templates/
  base.html                   # Navbar, footer, chatbot widget include
  index.html                  # Homepage
  products.html               # Product grid
  products_single.html        # Single product detail
  customer_login.html
  customer_register.html
  user_purchases.html         # Order history dashboard
  admin.html                  # Admin dashboard
  admin_login.html
  admin_config_review.html    # Dialogflow agent JSON audit page
  chatbot.html                # Chat widget (included in every page)
static/css/main.scss          # Source styles (compiled → main.css)
seed.py                       # Initial 5 customers + 8 orders
seed_more.py                  # 4 more customers + 17 orders + 10 tickets
seed_admin.py                 # Admin account
check_services.bat            # Verify Flask + ngrok are running
exported_agent_*/             # Dialogflow CX agent export (config review page)
```

---

## Dialogflow CX Agent

| | |
|---|---|
| GCP Project | `csci321-chatbot-for-cs` |
| Agent ID | `e7e8fe80-878e-484e-b3d7-76ff1222b47b` |
| Location | `asia-southeast1` |
| Webhook name | `verify_and_fetch_order` |

**Supported conversation flows:**

| Flow | Status |
|---|---|
| Track package (unauthenticated) | Complete |
| Track package (authenticated) | Complete |
| Change delivery address | Complete |
| Cancel order | Complete |
| Create support ticket | Complete |
| FAQ / general questions | Complete (fuzzywuzzy match) |

---

## Admin Features

| Path | Feature |
|---|---|
| `/admin/` | Ticket list (open-first), chatbot response manager |
| `/admin/config-review` | Dialogflow agent JSON audit |
| `/admin/import-template` | Bulk-load domain response templates |
| `/admin/tickets/<id>` PATCH | Update ticket status (open / resolved) |
| `/admin/tickets/<id>` DELETE | Delete a ticket |
| `/admin/responses` POST/DELETE | CRUD for bot response overrides |

---

## Common Issues

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` with venv activated |
| Webhook not receiving calls | Check ngrok is running and URL is updated in Dialogflow CX |
| `google.auth` errors | Confirm `serviceAccountKey.json` is in the project root |
| Database errors | Delete `orders.db` and re-run seed scripts |
| Port 5000 already in use | Kill the existing Python process or change port in `app.py` |
| ngrok URL changed | Restart `./ngrok.exe http 5000` and update webhook URL in Dialogflow CX |

---

## Important Notes

- **Never commit `serviceAccountKey.json`** — grants full GCP access
- **Never commit `.env`** — contains application secrets
- `orders.db` is gitignored — each developer maintains their own local database
- The `1.ref-storefront/` and `templates/old/` folders are read-only reference material — do not modify
- Edit `static/css/main.scss`, not `main.css` directly

---

## GitHub

Repository: [github.com/314AMBRTemp/CSIT321-ChatbotCS-FYP-26-S2-21P](https://github.com/314AMBRTemp/CSIT321-ChatbotCS-FYP-26-S2-21P)

Active development branch: `120626-project-RMH`
Production-ready branch: `main`
