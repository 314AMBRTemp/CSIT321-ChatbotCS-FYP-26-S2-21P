# AssistFlow — Project Context

## What This Is
AssistFlow is a Flask e-commerce storefront selling animal-themed ceramic cups. It includes customer auth, order tracking, an AI chatbot (Google Dialogflow CX), and an admin dashboard. It is a school FYP (CSIT321, group 26, S2 2026).

Run with: `python app.py` → `http://localhost:5000`
Expose publicly: `./ngrok.exe http 5000` (requires authtoken — see README(2).md)

---

## Tech Stack
- **Backend**: Flask 3.1.3, SQLAlchemy 3.1.1, Flask-Login 0.6.3, Flask-Bcrypt 1.0.1
- **Database**: SQLite (`orders.db`) — auto-created on first run via `db.create_all()`
- **Chatbot**: Google Dialogflow CX (`google-cloud-dialogflow-cx==2.5.0`), credentials via `serviceAccountKey.json`
- **FAQ fuzzy match**: `fuzzywuzzy==0.18.0` + `python-Levenshtein==0.27.3`
- **Frontend**: Bootstrap 4, jQuery, Themify Icons, Open Sans + Rajdhani (Google Fonts)
- **Auth**: `serviceAccountKey.json` must be present in the project root (gitignored)

---

## Project Structure

```
app.py                        # Flask app factory, blueprint registration, product routes
extensions.py                 # db, bcrypt, login_manager singletons
models.py                     # Admin, Customer, Order, Ticket, BotResponse
routes/
  admin.py                    # /admin/* — dashboard, tickets, response CMS, config review
  customer_auth.py            # /customer/login|register|dashboard|logout
  webhook.py                  # / (index), /chat (Dialogflow), /webhook (fulfillment)
templates/
  base.html                   # Navbar (auth-aware), footer, location modal, chatbot include
  index.html                  # Homepage — hero banner, promo, features, subscribe, contact
  products.html               # Product grid
  products_single.html        # Single product detail
  customer_login.html         # Branded sign-in page (site_banner_inner_products style)
  customer_register.html      # Branded register page
  user_purchases.html         # Authenticated order history dashboard
  admin.html                  # Admin dashboard — tickets + chatbot response manager
  admin_login.html            # Admin sign-in
  admin_config_review.html    # Dialogflow agent JSON audit page
  chatbot.html                # Chat widget — included in base.html
static/css/main.scss          # Source styles (compiled to main.css)
seed.py                       # Seeds 5 initial customers + 8 orders (only if tables empty)
seed_more.py                  # Seeds 4 additional customers + 17 orders (idempotent)
seed_admin.py                 # Seeds admin account (only if table empty)
1.ref-storefront/             # Original reference version — do not edit
templates/old/                # Archived old templates — do not edit
exported_agent_*/             # Dialogflow CX agent export — used by config review page
```

---

## Database Models

| Model | Table | Key Fields |
|---|---|---|
| `Admin` | `admins` | id, email, password_hash, name, last_login |
| `Customer` | `customers` | id, email, password_hash, name, last_login |
| `Order` | `orders` | order_id (PK, e.g. ORD-001), customer_email, status, courier, estimated_delivery, delivery_address |
| `Ticket` | `tickets` | ticket_id, order_id (FK), customer_email, issue_type, description, status |
| `BotResponse` | `bot_responses` | intent_id (PK), response_text, updated_at |

`BotResponse` stores admin-managed intent→response overrides used by the `faq_search` webhook tag.

User ID format for Flask-Login: `"a-{id}"` for admins, `"c-{id}"` for customers.

---

## Seed Accounts (all `password123` for customers, `admin123` for admin)

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

Total: 9 customers, 25 orders (ORD-001 through ORD-025).

---

## Brand & Design Conventions

**Colors:**
- `#344D68` — brand blue (headings, accents, auth card top border)
- `#111B25` — brand dark (body text, dark sections, button hover)
- `#00e095` — brand accent green (subscribe section, feature icons)
- `#0074f1` — Bootstrap `$primary` (links, form focus)
- `#ef1f3e` — Bootstrap `$danger` (error states)

**Typography:**
- `Rajdhani` (700) — section titles, auth headings, banners. Always `text-transform: uppercase`
- `Open Sans` — body text, nav links, form labels

**Card style:** `border-radius: 0 !important` site-wide. Auth cards use `border-top: 3px solid #344D68` as accent.

**Inner page banner:** Use `.site_banner_inner_products` (has `margin-top: 100px` for fixed navbar). Do NOT use `.site_banner_inner` for new pages — it lacks the top margin.

**CSS source:** Edit `static/css/main.scss`, compiled output is `main.css`. Do not edit `main.css` directly.

---

## Auth Flow

**Customer:** `/customer/login` → `customer_bp` in `routes/customer_auth.py`
- `login_user(customer, remember=remember)` — "Remember Me" checkbox supported
- On success → redirect to `/customer/dashboard` (renders `user_purchases.html`)
- Template variable: `customer=current_user` (not `user`) — `user_purchases.html` uses `customer.name`

**Admin:** `/admin/login` → `admin_bp` in `routes/admin.py`

**Navbar state:** `base.html` checks `current_user.is_authenticated` — shows My Orders + Logout when logged in, login icon when guest.

---

## Chatbot Architecture

**Widget:** `templates/chatbot.html` — included in every page via `{% include 'chatbot.html' %}` in `base.html`.

**Persistence (localStorage):**
- `chat_session_id` — Dialogflow session ID survives page navigation
- `chat_is_open` — window open/close state restored on page load
- `chat_history` — full message array replayed on load via `loadChatHistory()`
- On session expiry all three keys are cleared

**Inactivity timeout:**
- 5 minutes of no user message → warning bubble shown
- 1 more minute → session ended, input disabled, localStorage cleared

**Resize handles:**
- Three drag handles: `.chat-resize-nw` (corner), `.chat-resize-n` (top edge), `.chat-resize-w` (left edge)
- Window is anchored bottom-right, so dragging left/up expands it
- Limits: min `260×300px`, max `600×700px`

**Split-bubble responses:**
- `/chat` endpoint returns `{"replies": [...]}` — an array of strings
- Frontend loops through the array, showing a 600ms typing indicator between each bubble
- Each bubble is saved individually to `chat_history` in localStorage
- Typing indicators use `renderMsg('...', 'typing', false)` — not saved to history

**Dialogflow flow:**
1. User message → `POST /chat` → `detect_intent()` → Dialogflow CX
2. Dialogflow may call back `POST /webhook` for fulfillment (order lookups, address changes, ticket creation, FAQ search)
3. Webhook tags: `track_package`, `authenticated_track`, `change_delivery_address`, `cancel_order`, `create_ticket`, `faq_search`

**`faq_search` tag:** Uses `fuzzywuzzy` to match user query against `BotResponse.intent_id` values (threshold 60%). Falls back to "no match" message if below threshold.

**Session params injected:** `is_logged_in`, `customer_email`, `customer_name`, `order_id`, `package_status`, `estimated_delivery`, `courier`, `delivery_address` (when single active order exists).

---

## Admin Features

- `/admin/` — ticket list (sorted open-first), chatbot response manager
- `/admin/config-review` — reads `exported_agent_*/` files, displays intents, training phrases, flow routes
- `/admin/import-template` — bulk-loads domain response templates ("Website Navigation", "Customer Service", "Sales & Marketing")
- `/admin/responses` POST/DELETE — CRUD for `BotResponse` records
- Ticket statuses simplified to binary: `open` (Unsolved) / `resolved` (Solved)

---

## Known Issues / Watch Out For

- `serviceAccountKey.json` is gitignored and must be manually placed in project root to run the chatbot
- `static/css/main.css` references `url(../images/products/oTx.jpg)` but the file is `oTx.webp` — inner banner image won't load but gradient fallback shows fine
- `ngrok.exe` is gitignored — must be manually placed in root if needed
- `*.db` files are gitignored — run `seed.py`, `seed_admin.py`, `seed_more.py` after fresh clone to populate data
- The `1.ref-storefront/` folder is a read-only reference copy of the original project — do not modify it

---

## GitHub Remote
`https://github.com/314AMBRTemp/CSIT321-ChatbotCS-FYP-26-S2-21P.git`
Main branch (`main`) holds the production-ready version from `project-RMH`.
This folder (`120626-project-RMH`) is the active development version with extended features.
