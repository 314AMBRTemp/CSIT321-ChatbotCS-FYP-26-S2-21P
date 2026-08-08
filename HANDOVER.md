# AskIvy HRMS — Setup & Handover

Get the project running on a new machine: installing what's in the two
`requirements.txt` files, and running the 4 terminals needed for the full
Rasa + Claude chatbot. For architecture, design decisions, and how to extend
the bot, see `CLAUDE.md` — this doc is just "how do I get it running."

---

## What you're installing, and why there are two separate `requirements.txt`

| File | Installs into | Why separate |
|---|---|---|
| `backend/requirements.txt` | `backend/venv` | Flask API — works on any modern Python |
| `rasa/requirements.txt` | `rasa/.venv` | Rasa Pro — has its own pinned dependency tree that conflicts with Flask's, and needs a specific Python version (below) |

Never install one project's requirements into the other's virtualenv.

```
backend/requirements.txt          rasa/requirements.txt
├── Flask==3.0.3                  ├── rasa-pro>=3.18,<3.19
├── Flask-Cors==4.0.1              ├── requests>=2.32.0
├── Flask-SQLAlchemy==3.1.1       └── python-dotenv>=1.0.1
├── python-dotenv==1.0.1
└── requests==2.32.3
```

There's also `frontend/package.json` (npm, not pip) for the React widget —
covered in Terminal 4 below.

---

## Prerequisites

- **Node.js** (for the frontend) — any recent LTS.
- **Python 3.12 or 3.13 for `rasa/.venv`.** `rasa-pro` requires `>=3.10,<3.14`.
  If your only Python is 3.14.x (`python --version`), it **cannot** install
  Rasa Pro — you'll get "no matching distribution" from pip. `backend/venv`
  can use whatever Python you already have; only the Rasa side is picky.
- **A way to get Python 3.12/3.13 if you don't have it.** The
  [`uv`](https://docs.astral.sh/uv/) tool (`uv python install 3.12`) is the
  easiest — no installer, no admin rights, works per-project. If you use it,
  read the callout below before creating virtualenvs.
- **An Anthropic API key** (`ANTHROPIC_API_KEY`) and **a Rasa Pro licence key**
  (`RASA_LICENSE`) — free developer tier at
  rasa.com/rasa-pro-developer-edition/.

> ⚠️ **If you installed Python via `uv`, `py -3.12` will not find it.** `uv`
> registers interpreters under its own tag (e.g. `Astral/CPython3.12.13`), not
> the plain `-3.12` alias the Windows `py` launcher looks for. Use `uv` itself
> to create the virtualenv instead of `py -3.12 -m venv`:
> ```powershell
> uv venv --python 3.12 <venv-dir>
> uv pip install -p <venv-dir>\Scripts\python.exe -r requirements.txt
> ```
> If your Python came from python.org or the Microsoft Store instead, the
> normal `py -3.12 -m venv venv` / `pip install -r requirements.txt` works fine.

---

## One-time setup

### 1. Backend (`backend/venv`)

```powershell
cd backend
python -m venv venv                          # or: uv venv --python 3.12 venv
venv\Scripts\activate
pip install -r requirements.txt               # or: uv pip install -p venv\Scripts\python.exe -r requirements.txt
```

No `.env` needed for local dev — it defaults to a local SQLite file and CORS
open to `*`.

### 2. Rasa (`rasa/.venv`)

```powershell
cd rasa
uv venv --python 3.12 .venv                   # must be 3.12 or 3.13, not 3.14
uv pip install -p .venv\Scripts\python.exe -r requirements.txt
```

This installs `rasa-pro` and pulls in `rasa_sdk` (the action-server library)
as a dependency automatically — nothing extra to install for that.

Then set up secrets:

```powershell
copy .env.example .env
notepad .env
```

Fill in:

```
ANTHROPIC_API_KEY=sk-ant-...
RASA_LICENSE=<your Rasa Pro key>
ASKIVY_API_URL=http://localhost:5000
```

> ⚠️ **The env var is `RASA_LICENSE`, not `RASA_PRO_LICENSE_KEY`.** The
> installed Rasa build's actual license check
> (`rasa/utils/licensing.py`) reads `RASA_LICENSE`. The value is the same
> either way — only the variable name matters.

`rasa/.env` is gitignored — never commit it, and never put real keys in
`rasa/.env.example` (that file is the template, meant to be shared/committed).

### 3. Frontend (`frontend/`)

```powershell
cd frontend
npm install
```

### 4. Train the Rasa model (once, or after editing `domain.yml`/`flows.yml`)

```powershell
cd rasa
.venv\Scripts\activate
# load .env into the shell — see the loader snippet in "Running it" below
$env:PYTHONUTF8 = "1"
rasa train
```

This produces a `.tar.gz` model file in `rasa/models/`. `rasa run` loads
whatever's newest in that folder — you don't reference it by name.

---

## Running it — 4 terminals, all at once

This is the part that trips people up: **you need four separate terminal
windows running simultaneously**, not three. It's easy to think "backend +
Rasa server + frontend" is the whole set and forget the Rasa **action**
server — it's a distinct process from the Rasa server itself, on its own
port, and the chatbot silently fails on every real question without it.

| # | What | Command | Port |
|---|---|---|---|
| 1 | Flask backend | `python app.py` | `:5000` |
| 2 | Rasa action server | `rasa run actions` | `:5055` |
| 3 | Rasa server | `rasa run --enable-api --cors "*"` | `:5005` |
| 4 | Frontend | `npm run dev` | `:5173` |

None of these exit back to a prompt when working correctly — if a window
goes back to a plain prompt, that service has stopped and needs restarting.

### Terminal 1 — Flask backend

```powershell
cd backend
venv\Scripts\activate
python app.py
```

Verify: `http://localhost:5000/api/health` → `{"status":"ok"}`.

### Terminal 2 — Rasa action server

```powershell
cd rasa
.venv\Scripts\activate
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#][^=]*)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2])
    }
}
$env:PYTHONUTF8 = "1"
rasa run actions
```

Wait for: `Action endpoint is up and running on http://0.0.0.0:5055`.

### Terminal 3 — Rasa server

Same env-loading step, then:

```powershell
cd rasa
.venv\Scripts\activate
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#][^=]*)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2])
    }
}
$env:PYTHONUTF8 = "1"
rasa run --enable-api --cors "*"
```

Wait for: `Rasa server is up and running.`

### Terminal 4 — Frontend

```powershell
cd frontend
npm run dev
```

To point the widget at the Rasa engine instead of the original rule-based
one, create `frontend/.env.local`:

```
VITE_ASKIVY_ENGINE=rasa
```

(Delete the file, or set it to `rules`, to switch back — both engines stay
live so you can compare them.)

---

## `$env:PYTHONUTF8 = "1"` — don't skip this

Bot replies containing non-ASCII characters (em dashes, arrows, bullets) can
come back corrupted on Windows without this — not just a display glitch, the
actual bytes sent to the frontend get mangled. Set it before starting **both**
Rasa terminals (2 and 3). It's cheap insurance even if your data happens to be
pure ASCII today.

---

## Quick health check, all four services

```powershell
curl http://localhost:5000/api/health           # Flask
curl http://localhost:5055/health               # Rasa action server
curl http://localhost:5005/status               # Rasa server
curl http://localhost:5000/api/askivy/rasa/health  # Flask's view of Rasa
```

The last one is the most useful single check — it tells you whether Flask can
reach the Rasa server *and* whether a trained model is loaded, in one call.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `pip install rasa-pro` → "no matching distribution" | Wrong Python version on that venv — needs `3.10`–`3.13`, not `3.14`. If using `uv`, use `uv venv --python 3.12`, not `py -3.12`. |
| Widget shows "having trouble with that" / bot cancels the flow it just started | The **action server** (terminal 2) isn't running or isn't reachable — check `curl http://localhost:5055/health`. This is the single most common gap: 3 terminals running instead of 4. |
| Widget: "can't reach AskIvy's reasoning service" | The **Rasa server** (terminal 3) isn't running — check `curl http://localhost:5005/status`. |
| Rasa won't start, license error | `RASA_LICENSE` not set in *that* terminal — env vars don't carry across windows, and `.env` isn't auto-loaded (see the `Get-Content` loader above). |
| Garbled characters in bot replies | `PYTHONUTF8=1` wasn't set before starting terminals 2/3. |
| Edited `domain.yml` or `data/flows.yml` but nothing changed | `rasa run` loads the model that was baked in at the last `rasa train` — it doesn't read those files live. Retrain, then restart terminal 3 (and terminal 2 if `actions.py` also changed). |
| "Device or resource busy" deleting `backend/instance/askivy_hrms.db` | Terminal 1 still has the file open. Stop it (Ctrl+C) first, delete, then restart — it reseeds automatically. |
| 404 from Anthropic | Model id in `rasa/endpoints.yml` is retired — see `CLAUDE.md` → "Model choice." |

For anything deeper — architecture, adding new flows/actions, the design
rationale behind specific choices — see `CLAUDE.md`.
