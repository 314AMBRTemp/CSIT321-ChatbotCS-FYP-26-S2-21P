# AskIvy HRMS — Project Guide

Final-year project: an HR management web app whose chatbot is being moved from a
hand-written rule engine to a Rasa CALM assistant that uses Claude as its
language-understanding layer.

**Stack:** React (Vite) · Flask + SQLAlchemy · SQLite local / Postgres prod ·
Rasa Pro (CALM) + Claude · deploy target Render.

---

## The mental model

```
ChatWidget (React :5173)
   └─ POST /api/askivy/chat-rasa            Flask adapter (:5000)
        └─ POST /webhooks/rest/webhook      Rasa server (:5005)
             ├─ CompactLLMCommandGenerator → asks Claude "what does the user want?"
             │                                returns StartFlow / SetSlot commands
             └─ FlowPolicy                  → executes the matching flow deterministically
                  └─ custom action          Rasa action server (:5055)
                       └─ GET/POST          back into the Flask HRMS API (:5000) → DB
```

One pipeline, two roles: **Claude does language understanding, Rasa does
deterministic flow and slot structure.** They are not two competing NLU tracks —
Rasa delegates understanding to Claude and keeps control of what happens next.

The adapter exists so the React widget never learns which engine answered: both
`/api/askivy/chat` (rules) and `/api/askivy/chat-rasa` (Rasa) return byte-identical
JSON shapes.

---

## Current state — verified 2026-07-26 (Stage 2 fully working, end to end)

### Working and tested — the whole pipeline, with real Claude calls
- Base Flask app: factory, models, seeded demo data, all REST routes.
- Rule-based chatbot (`services/askivy_engine.py`) — the original engine, untouched.
- **All 5 Rasa flows verified against live Claude output**, sender-scoped as the
  real seeded employees, hitting the real Flask API — not a mock:
  - `check_leave_balance` — correct numbers straight from Sarah's HRMS record
    (21 entitlement − 9 taken = 12 remaining).
  - `apply_for_leave` — one-shot slot fill ("Book me 2 days of sick leave") then
    confirmation, and the request **actually landed in the database**
    (`GET /api/employees/marcus/leave` shows it, `Pending`, `submittedVia: AskIvy`).
    The invalid-leave-type rejection was also exercised and correctly re-asks.
  - `compassionate_leave` — filled the `relationship` slot directly from
    "My mother passed away last night" in the *same turn* that started the flow
    (no follow-up question needed), correctly classified as immediate family (5
    days). Extended family ("my cousin") correctly classified separately (2 days).
  - `parental_eligibility` — correct for both the eligible case (Sarah, 7 years)
    and the ineligible case (Marcus, 0 years, in probation).
  - `policy_question` — retrieved the right policy for both "notice period" and
    "work from home", with rules quoted from the actual policy JSON.
- Verified through the real path the widget uses:
  `ChatWidget → /api/askivy/chat-rasa → Rasa REST channel → CompactLLMCommandGenerator
  (Claude) → FlowPolicy → action server → Flask API`, not just the raw Rasa webhook.
- Python 3.12.13 installed via `uv`; `backend/venv` and `rasa/.venv` both recreated
  against it and fully populated. `rasa-pro==3.18.1` + `rasa_sdk==3.18.0` installed.

### Two real bugs found during this run and fixed

1. **pypred (Rasa's predicate language) has no `in` / list syntax.** The
   `leave_type` rejection in `data/flows.yml` originally read
   `slots.leave_type not in ['Annual', 'Sick', 'Compassionate', 'Parental']`,
   which is valid Python but not valid pypred — `rasa train` failed validation
   with an opaque parser error pointing at the list literal. Fixed to the
   chained-comparison form pypred actually supports:
   `slots.leave_type != 'Annual' and slots.leave_type != 'Sick' and ...`.
   Verified both that `rasa train` now passes and that the rejection actually
   fires correctly at runtime.

2. **Non-ASCII punctuation (em dash, bullet, middle dot) in bot-facing text
   got corrupted in transit on this machine.** `curl -o file` on the raw HTTP
   response showed the literal 5-byte ASCII string `u2022` in place of a bullet
   character — not a terminal display issue, the wire bytes themselves were
   wrong. Root cause: this Windows console's stdout is `cp1252`; something in
   Rasa's internal logging path hits `UnicodeEncodeError` on non-ASCII text and
   falls back to a lossy substitution that strips the backslash from a
   `•`-style escape, and that mangled text gets reused as the actual
   payload, not just logged. Fixed two ways: replaced every em dash / bullet /
   middle dot in `actions/actions.py` and `domain.yml` with ASCII (`--`, `-`,
   `|`), **and** set `PYTHONUTF8=1` before launching the action server and Rasa
   server. Do both when you next touch either file — see "Design decisions"
   below for the standing rule.

> **License env var correction.** The installed build's actual check
> (`rasa/utils/licensing.py`) reads **`RASA_LICENSE`**, not `RASA_PRO_LICENSE_KEY`
> as an earlier draft of this doc assumed. `.env.example` and the commands below
> use the correct name.

> **`py -3.12` does not work on this machine.** `uv`-installed interpreters
> register under a vendor tag (`Astral/CPython3.12.13`), not the plain `-3.12`
> alias the `py` launcher shorthand expects. Use `uv venv --python 3.12 <dir>` to
> create venvs and `uv pip install -p <dir>/Scripts/python.exe -r requirements.txt`
> to install into them — that is what actually works here. The commands below are
> written for that.

### Not yet done
- `rasa test e2e tests/e2e_test_cases.yml` hasn't been run — the 10 scripted
  cases should now pass given the manual pass above, but haven't been executed
  as a suite. Good next step for report evidence.
- No test of the frontend widget itself with `VITE_ASKIVY_ENGINE=rasa` — only
  the API layer has been exercised directly.

### Nothing currently blocked
Both keys are in `rasa/.env` (gitignored — never commit it), both venvs are
populated, and a trained model exists in `rasa/models/`. Stage 2 in "Running it"
below now describes a working setup, not a first attempt.

---

## Outstanding backend bugs (NOT yet fixed)

These were described as done in an earlier handoff document but are not present in
the code. Worth fixing before the demo — the first one is a genuine data bug.

| # | Issue | Location |
|---|---|---|
| 1 | **Annual leave deducted on submission, not approval.** A rejected request permanently consumes the balance, and there is no approve/reject route at all. | [app.py:93](backend/app.py#L93), [app.py:147](backend/app.py#L147) |
| 2 | No `PATCH /api/leave/<id>/status` to approve/reject and do the accounting. | [app.py](backend/app.py) |
| 3 | `datetime.utcnow` is deprecated in Python 3.12+; use a timezone-aware helper. | [models.py:55](backend/models.py#L55), [models.py:80](backend/models.py#L80) |
| 4 | Sick-leave entitlement is hardcoded `14` instead of an `Employee` column. | [askivy_engine.py:19](backend/services/askivy_engine.py#L19) |
| 5 | `int(payload.get("days", 1))` throws a 500 on bad input; should be a 400. | [app.py:130](backend/app.py#L130) |
| 6 | CORS defaults to `"*"`; should default to `http://localhost:5173`. | [app.py:26](backend/app.py#L26) |
| 7 | Frontend deps are all `"latest"` — non-reproducible builds. | [frontend/package.json](frontend/package.json) |
| 8 | Missing `psycopg2-binary` + `gunicorn` for the Render deploy. | [backend/requirements.txt](backend/requirements.txt) |

**Policy files — clarification.** The running app reads
`backend/data/hr_policies.json` ([policy_repository.py:5](backend/services/policy_repository.py#L5)).
The two files under `policies/` are *documentation only* and are read by nothing.
Editing `policies/hr-policies.md` does not change assistant behaviour.

---

## Layout

```
AskIvy/
├── backend/                       Flask API (:5000)
│   ├── app.py                     routes, app factory, seed data
│   ├── models.py                  Employee, LeaveRequest, ChatMessage
│   ├── data/hr_policies.json      ← the policy source the app actually reads
│   ├── data/career_paths.json     ← career-transition dataset (5 department pairs)
│   └── services/
│       ├── askivy_engine.py       rule-based chatbot (kept for comparison)
│       ├── policy_repository.py   keyword policy retrieval
│       ├── career_repository.py   career-path lookup (mirrors policy_repository.py)
│       └── rasa_adapter.py        Flask ↔ Rasa bridge blueprint
├── frontend/                      React + Vite (:5173)
│   └── src/{App.jsx, api.js, components/ChatWidget.jsx}
├── rasa/                          Rasa CALM assistant
│   ├── config.yml                 CompactLLMCommandGenerator → Claude; FlowPolicy
│   ├── endpoints.yml              Claude model group + action server URL
│   ├── credentials.yml            REST channel
│   ├── domain.yml                 slots, responses, action names
│   ├── data/flows.yml             6 flows
│   ├── actions/actions.py         6 custom actions
│   └── tests/e2e_test_cases.yml   10 end-to-end test cases (career path not yet added)
├── policies/                      documentation copies (unused by code)
├── docs/                          architecture.md, demo-script.md
└── misc/                          standalone HTML mockup (no dependencies)
```

**Ports:** Flask 5000 · Rasa 5005 · Rasa actions 5055 · frontend 5173.

### API routes
`GET` `/api/health` · `/api/users` · `/api/employees/<id>[/dashboard|/leave]` ·
`/api/policies` · `/api/policies/search?q=` · `/api/careers/search?from=&to=` ·
`/api/askivy/rasa/health`
`POST` `/api/employees/<id>/leave` · `/api/askivy/chat` · `/api/askivy/chat-rasa` ·
`/api/askivy/submit-leave` · `/api/askivy/rasa/reset`

### Flows and actions
| Flow | Action | Does |
|---|---|---|
| `check_leave_balance` | `action_get_leave_balance` | Reports annual + sick balances |
| `apply_for_leave` | `action_submit_leave` | Collects type/days/confirmation, files the request |
| `compassionate_leave` | `action_compassionate_leave` | Classifies relationship, recommends 5 or 2 days |
| `parental_eligibility` | `action_check_parental_eligibility` | Checks 12-month service rule |
| `policy_question` | `action_policy_answer` | Cites policy rules via `/api/policies/search` |
| `career_path_advice` | `action_career_path_advice` | Recommends certs/steps for a department move, via `/api/careers/search` |

**Career paths — data-driven, not generated.** Same rule as policies: the bot
cites `backend/data/career_paths.json`, it never asks Claude to invent a plan.
If no path is defined for the requested (from, to) pair, it says so honestly
and offers whatever alternatives exist from the employee's own department —
verified for both the "alternatives exist" and "zero alternatives" cases. The
employee's *current* department comes from their real HRMS record; only the
*target* department is collected from the conversation.

### Employee roster
Expanded from 2 to 14 employees across 5 departments so the career-path
feature (and the app generally) has real headcount to test against, not just
strings in a JSON file:

| Department | Employees |
|---|---|
| Engineering | sarah, david, priya, aiden |
| Product | marcus, ethan |
| Design | meiling, farah |
| Sales | rachel, kevin, nurul |
| Operations | weijian, siti, junwei |

`siti` (Operations, 2 years tenure) has `recentEvent: "Interested in moving into
Sales"` as a deliberate demo hook for `career_path_advice`. Sarah and Marcus are
untouched from the original 2-employee seed — their exact values are referenced
by `tests/e2e_test_cases.yml` and elsewhere, so don't change their fields
without checking those references first.

**If you add/change seed employees again:** `seed_demo_data()` only runs on an
empty database (`if Employee.query.first(): return`). Editing the seed code
does nothing to an already-seeded DB — delete `backend/instance/askivy_hrms.db`
(Flask must not be running, or the delete fails with "device or resource busy")
and restart `python app.py` to reseed.

---

## Design decisions worth knowing

**Employee identity = Rasa `sender_id`.** The adapter posts
`{"sender": "<employeeId>"}`, so `tracker.sender_id` inside every action is the HRMS
employee id. Consequence: conversation state persists per employee across demo runs —
a half-finished `apply_for_leave` will resume. `POST /api/askivy/rasa/reset` clears it.

**Actions never touch the database.** They call the Flask REST API, so leave
accounting has exactly one implementation. This is also why `/api/policies/search`
exists — both chat engines cite the same policies for the same question.

**Flow retrieval is disabled** in `config.yml`. It shortlists flows when you have
dozens; with 5 they all fit in the prompt. Enabling it pulls in an embedding model
(~2 GB of torch) or a second API key for no benefit at this scale.

**Metadata channel.** Actions emit two messages — plain text, plus
`json_message={"askivy": {...}}` carrying `source` / `isRecommendation` /
`canSubmitLeave` / `suggestedLeave` / `thinkingSteps`. The adapter merges them into
the widget's existing shape. A flow that only utters a domain response still works;
it just carries neutral metadata.

**Model choice — do not skip this.** `claude-3-7-sonnet-*` (the id in the earlier
handoff) was **retired 2026-02-19 and now 404s**. `endpoints.yml` uses
`claude-sonnet-4-5`, which is current *and* still accepts `temperature: 0` —
command generation wants determinism. If you upgrade to `claude-sonnet-5` you must
**delete the `temperature` line**, because it rejects non-default sampling
parameters with a 400. Swapping the model id alone will break it.

**Bot-facing text is ASCII-only — keep it that way.** Em dashes, bullets, and
middle dots in `actions/actions.py` or `domain.yml` corrupted in transit on this
Windows dev machine (see "Two real bugs" above) — the wire bytes themselves came
out wrong, not just a terminal display glitch. Use `--`, `-`, `|`. If you must use
non-ASCII text, launch the action server and Rasa server with `PYTHONUTF8=1` set
first (`export PYTHONUTF8=1` before the `rasa run` commands in Stage 2) — that
addresses the root cause, the ASCII-only rule is the belt-and-suspenders half.

---

## Running it

### Stage 1 — base app (no keys needed)

**Already done as of this session** — `backend/venv` was recreated against Python
3.12.13 (installed via `uv python install 3.12`) and verified to boot. Just run it:

```powershell
cd backend
venv\Scripts\activate
python app.py                  # :5000, seeds the DB on first boot
```

If you need to redo it from scratch (e.g. on a different machine), `py -3.12`
does **not** resolve a `uv`-installed interpreter here — use `uv` directly:

```powershell
cd backend
Remove-Item -Recurse -Force venv
uv venv --python 3.12 venv
uv pip install -p venv\Scripts\python.exe -r requirements.txt
venv\Scripts\activate
python app.py
```

Verify `http://localhost:5000/api/health` → `{"status":"ok"}`.

```powershell
cd frontend; npm install; npm run dev     # :5173
```

Log in as Sarah Tan, open AskIvy, and ask *"How many leave days do I have?"* and
*"My cousin passed away, is there leave for this?"* — that is the **rule-based**
engine. Confirm this works before Stage 2.

> `gunicorn` will not run on Windows locally — expected, it is only for Render.

### Stage 2 — Rasa + Claude (4 terminals)

**Already set up and verified working** — `rasa/.env` has both real keys,
`rasa/.venv` is populated with `rasa-pro==3.18.1`, and a trained model exists in
`rasa/models/`. Every flow has been exercised against live Claude output (see
"Current state" above). This is now a known-good path, not a first attempt.

```powershell
cd rasa
.venv\Scripts\activate
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#][^=]*)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2])
    }
}
$env:PYTHONUTF8 = "1"    # avoid the console-encoding bug — see "Design decisions"
```

If setting up fresh (new machine, keys rotated): copy `.env.example` to `.env`,
fill in `ANTHROPIC_API_KEY` and `RASA_LICENSE`, then load it the same way. If
`rasa/.venv` doesn't exist yet, recreate it the same way as `backend/venv` above
(`uv venv --python 3.12 .venv`, then `uv pip install`).

| Terminal | Command |
|---|---|
| T1 Flask | `cd backend; venv\Scripts\activate; python app.py` |
| T2 actions | `cd rasa; .venv\Scripts\activate; $env:PYTHONUTF8="1"; rasa run actions` |
| T3 Rasa | `cd rasa; .venv\Scripts\activate; $env:PYTHONUTF8="1"; rasa run --enable-api --cors "*"` |
| T4 frontend | `cd frontend; npm run dev` |

Re-run `rasa train` only after changing `domain.yml` or `data/flows.yml` —
`rasa run` loads the domain baked into the trained model artifact, not live from
disk, so editing either file has no effect until you retrain. `actions.py`
changes only need an action-server restart (T2), no retrain.

Then point the widget at Rasa — create `frontend/.env.local`:

```
VITE_ASKIVY_ENGINE=rasa
```

and restart `npm run dev`. Remove the line (or set `rules`) to switch back; both
routes stay live, which is what makes side-by-side comparison possible for the report.

**Check it before demoing:** `http://localhost:5000/api/askivy/rasa/health` should
report `"status":"ok"` with a model file. `"no_model_loaded"` means `rasa train`
hasn't finished; `"unreachable"` means the Rasa server isn't up.

Fastest sanity check without the UI: `rasa inspect` (live flow stack + slots).

### Tests
```powershell
cd rasa; .venv\Scripts\activate; rasa test e2e tests/e2e_test_cases.yml
```
Needs the action server *and* Flask running — the actions call the live API. The
cases assert on flows and slots rather than exact bot wording, because action text
is built from live HRMS data.

---

## Deployment (Render)

- **Backend service:** root `backend`, build `pip install -r requirements.txt`,
  start `gunicorn app:app`, env `DATABASE_URL` (internal Postgres URL — the code
  rewrites `postgres://` → `postgresql://`) and `FRONTEND_ORIGIN`.
- **Static site:** root `frontend`, build `npm install && npm run build`,
  publish `dist`, env `VITE_API_URL`.
- Free Postgres expires ~30 days after creation (14-day grace) — create it near the
  demo date; the app reseeds automatically on a fresh DB.
- Free web services sleep after 15 min (~60 s cold start) — hit `/api/health` first.
- **Rasa is too heavy for a free Render service — run it locally during the demo.**
  This means the deployed site must use `VITE_ASKIVY_ENGINE=rules`.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `pip install rasa-pro` → "no matching distribution" | Wrong Python on the venv. Needs `>=3.10,<3.14`; use `uv venv --python 3.12`, not `py -3.12` (see note above). |
| Widget: "can't reach AskIvy's reasoning service" | Rasa not running. Check `/api/askivy/rasa/health`. |
| `rasa/health` says `no_model_loaded` | `rasa train` not run or still going. |
| Rasa won't start, license error | `RASA_LICENSE` (not `RASA_PRO_LICENSE_KEY`) not set *in that terminal*. |
| CORS error | Missing `--cors "*"` on Rasa, or wrong `FRONTEND_ORIGIN` on Flask. |
| 404 from Anthropic | Retired model id — see "Model choice" above. |
| 400 about `temperature` | Using `claude-sonnet-5` with `temperature` still set. |
| Bot resumes an old half-finished flow | Tracker persists per employee. `POST /api/askivy/rasa/reset`. |
| `rasa train` fails on a `rejections`/`if:` predicate | pypred has no `in` / list syntax — `not in [...]` is invalid even though it's valid Python. Use chained `!=`/`and`/`or` instead. See "Two real bugs" above. |
| Bot text shows garbled characters or literal `u2022`-style text | Non-ASCII punctuation (em dash, bullet, middle dot) in `actions.py` or `domain.yml`, corrupted by this machine's `cp1252` console. Use ASCII (`--`, `-`, `|`) and set `PYTHONUTF8=1` before launching Rasa. |
| Edited `domain.yml` or `flows.yml` but nothing changed | `rasa run` loads the domain baked into the trained model, not live from disk. Re-run `rasa train` first. |
| Config rejected on train | Installed Rasa differs from the assumed 3.18 layout. Run `rasa init --template calm` in a scratch dir and reconcile `config.yml` / `endpoints.yml` / `domain.yml`. `flows.yml` and `actions.py` are the portable parts. |

---

## Next steps, in order

1. ~~Install Python 3.12 or 3.13; recreate `backend/venv`.~~ Done.
2. ~~Run Stage 1 and confirm the rule-based engine still works.~~ Done.
3. ~~Obtain the Rasa Pro licence key and Anthropic key.~~ Done — in `rasa/.env`.
4. ~~Run Stage 2 against real Claude output.~~ Done — all 5 flows verified, see
   "Current state" above.
5. Run `rasa test e2e tests/e2e_test_cases.yml` as a suite and capture the output
   as validation evidence for the report — the 10 cases should pass given the
   manual pass already done, but haven't been run together.
6. Test the frontend widget itself with `VITE_ASKIVY_ENGINE=rasa` set — only the
   API layer has been driven directly so far, not the React UI.
7. Fix the outstanding backend bugs — start with the leave-balance accounting (#1/#2).
