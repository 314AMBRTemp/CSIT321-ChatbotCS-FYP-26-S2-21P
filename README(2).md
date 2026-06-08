# AssistFlow — Setup & Run Guide

A Flask-based storefront with order tracking, customer login, and an AI chatbot powered by Google Dialogflow CX.

---

## Prerequisites

- Python 3.10 or higher — [python.org/downloads](https://www.python.org/downloads/)
- pip (comes bundled with Python)

---

## 1. Download the Code

1. Go to the GitHub repository page
2. Click the green **Code** button → **Download ZIP**
3. Extract the ZIP to a folder of your choice (e.g. `C:\Projects\AssistFlow`)

---

## 2. Install Dependencies

Open a terminal and navigate to the extracted folder:

```bash
cd path/to/AssistFlow
```

Install all required packages:

```bash
pip install -r requirements.txt
```

---

## 3. Run the App

```bash
python app.py
```

The terminal will show:

```
* Running on http://127.0.0.1:5000
```

Open your browser and go to:

```
http://localhost:5000
```

---

## 4. Expose Publicly via ngrok (Optional)

ngrok lets you share the app over the internet with a public URL — useful for demos or webhook testing.

### 4a. Create a Free ngrok Account

1. Go to [ngrok.com](https://ngrok.com) and sign up for a free account
2. After signing in, go to **Your Authtoken** in the dashboard: [dashboard.ngrok.com/get-started/your-authtoken](https://dashboard.ngrok.com/get-started/your-authtoken)
3. Copy your authtoken (looks like `2abc...xyz`)

### 4b. Authenticate ngrok

Run this once to save your token:

```bash
./ngrok.exe config add-authtoken YOUR_AUTHTOKEN_HERE
```

Replace `YOUR_AUTHTOKEN_HERE` with the token you copied.

### 4c. Start ngrok

Make sure `python app.py` is already running in one terminal, then open a **second terminal** in the same folder and run:

```bash
./ngrok.exe http 5000
```

ngrok will display a public URL like:

```
Forwarding   https://a1b2-123-456-789.ngrok-free.app -> http://localhost:5000
```

Open that URL in any browser (or share it with others) to access the live site.

> **Note:** The free ngrok URL changes every time you restart ngrok. Upgrade to a paid plan for a fixed domain.

---

## Seed Data (Test Accounts)

Run the following once after first launch to populate the database with sample customers and orders:

```bash
python seed.py
python seed_admin.py
```

| Role | Email | Password |
|---|---|---|
| Admin | admin@shopbot.com | admin123 |
| Customer | alice@email.com | password123 |
| Customer | bob@email.com | password123 |

Customer login: `/customer/login` — Admin login: `/admin/login`
