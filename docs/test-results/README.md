# Test & Measurement Evidence

Two suites, proving different things. Neither is sufficient alone — the split matters and
is explained below.

| Suite | Proves | Run with |
|---|---|---|
| **Rasa e2e** (`rasa/tests/e2e_test_cases.yml`) | Claude routes to the right flow and fills the right slots | `rasa test e2e …` |
| **API checks** (`tests/api_checks.py`) | The answers are factually correct against real HRMS data | `backend\.venv\Scripts\python.exe tests\api_checks.py` |

Both need Flask (`:5000`), the action server (`:5055`) and the Rasa server (`:5005`) up.

---

## 1. Rasa end-to-end — 15 / 15, 100% on every assertion type

```powershell
cd rasa
.venv\Scripts\activate
rasa test e2e tests/e2e_test_cases.yml -o ../docs/test-results/e2e-results.yml --coverage-report --coverage-output-path ../docs/test-results/coverage
```

| Assertion type | Accuracy |
|---|---|
| `flow_started` | 100.00% |
| `action_executed` | 100.00% |
| `slot_was_set` | 100.00% |
| `bot_uttered` | 100.00% |

Every case runs against **live Claude output** — a real Anthropic API call per turn, not
recorded fixtures. That makes this meaningful evidence for the part of the system that is
non-deterministic.

### ⚠️ What this suite does NOT prove

**Rasa sets `sender_id` to the test case name plus a timestamp.** In this system
`sender_id` *is* the HRMS employee id (see the module docstring in `rasa/actions/actions.py`).
So every e2e test runs against an employee that **does not exist**, every HRMS-backed action
takes its API-unreachable branch, and the bot actually replies:

> "I can't reach the HRMS right now, so I don't want to guess at your numbers."

The assertions still pass, because `action_executed` checks that an action *ran*, never what
it *returned*. Verified directly by posting a test-shaped sender to the Rasa REST webhook and
comparing against a real employee id.

The comment at the top of `e2e_test_cases.yml` claiming the cases "exercise the seeded
employees" reflects the original intent, not the behaviour — the runner overrides the sender.

**Consequence:** this suite validates routing. Suite 2 validates answers. Quoting "15/15
passing" as evidence the assistant answers correctly would be wrong.

### Flow coverage — 86.96% (20 of 23 steps)

| Flow | Coverage | Missing |
|---|---|---|
| check leave balance · apply for leave · compassionate leave · parental eligibility · policy question · career path advice | 100% | — |
| **cancel leave** | **57.14%** | 3 steps |
| **Total** | **86.96%** | 3 |

The `cancel_leave` gap is **structural, not an oversight**. Its uncovered steps are the
successful cancellation, the decline branch, and the multi-pending branch — all of which sit
behind `action_find_pending_leave` finding at least one pending request. It never can, because
the employee doesn't exist, so `pending_leave_count` is always 0 and only the zero-pending
branch is reachable.

Those three paths are covered by suite 2 instead, which is the right place for them — it can
seed the pending requests each branch needs. Between the two suites all four branches of
`cancel_leave` are now exercised: zero-pending here, and confirm / decline / multi-pending
there.

Note also that `career_path_advice` shows 100% while its action bailed at the API-down branch
before doing any career lookup — a good illustration of what step coverage does and doesn't
tell you here.

### Regression guards

Two of the fifteen exist because of real defects found in this project:

- *"a compassionate leave policy question is not treated as a bereavement"* — the flow used to
  swallow neutral policy questions and open with "I'm sorry for your loss".
- *"declining the HR follow-up after career advice"* — covers the branch that files nothing.

### Files

| File | What it is |
|---|---|
| `e2e-results_passed.yml` | Transcript of each passing case |
| `e2e-results_failed.yml` | Empty — no failures |
| `coverage/coverage_report_for_passed_tests.csv` | Per-flow coverage |
| `coverage/commands_histogram_for_passed_tests.png` | Distribution of commands Claude generated |

---

## 2. API checks — 32 / 32

```powershell
backend\.venv\Scripts\python.exe tests\api_checks.py
```

Drives the same endpoints the widget uses, with **real seeded employee ids**, and asserts on
the content of the reply. Exits non-zero on failure, so it can gate a commit.

| Group | What it verifies |
|---|---|
| Real data reaches the reply | The balance quoted matches `employee_facts()`, and is not the API-down message |
| Compassionate day counts | mother → 5, cousin → 3, mother-in-law → 3, **on both engines** — the four policy contradictions corrected on 2026-08-09 |
| Senior parental top-up | Rachel (Head of Sales) and Mei Ling (Lead) get it; Priya (Software Engineer) does not |
| Career path + handoff | Real certification cited, transfer requirement cited, no-match hands off to HR with department context |
| Policy vs bereavement | A policy lookup returns policy text and no condolences |
| **Cancel restores balance** | Submit deducts a day, cancel restores it, no pending left behind |
| **Declining keeps the request** | A decline leaves the request Pending and the balance untouched — a decline that silently cancelled would be the worst failure this feature could have |
| **Multi-pending disambiguation** | With one Annual and one Sick request pending, the bot asks *which*, cancels the Sick one, and leaves the Annual one alone |
| Support access | Admin 200, non-admin 403, no requester 403 |

The three cancel checks are **self-seeding and idempotent**: each clears any pending requests
left by an earlier run, creates exactly what it needs, drives the flow through chat, then
cleans up. Verified by running twice in succession, with both affected employees ending at
zero pending.

### Why these three matter disproportionately

They cover the paths e2e structurally cannot reach — and until they were written, the
multi-pending branch had **never executed once**, in any test or manual check. Every employee
exercised by hand happened to have exactly one pending request, so `_match_pending()` — the
function that decides *which* record to cancel — was entirely unrun code. It passed first time,
but that was not knowable beforehand.

Multi-pending is not an edge case in production: approval lag, block-booking, and this
company's own carry-over expiry on 31 March (`LEAVE-01`) all produce employees holding several
pending requests at once.

---

## 3. Latency — 2026-08-10

Measured warm (first call after restart discarded), 3 rounds, via `/api/askivy/chat-rasa`.

| Interaction | Before | After | LLM calls after |
|---|---|---|---|
| Completed flow | ~8.3s | **~6.0s** | 2 |
| Mid-flow question | ~3.6s | ~4.5s | 1 |
| Chitchat | ~5.1s | ~4.8s | 2 |
| Rule-based engine, same question | — | **37ms** | 0 |

**What produced the gain:** `utter_ask_continue_conversation` — the "anything else?" tail on
every completed flow — was being rewritten by the NLG rephraser, costing a full extra LLM
round trip to reword one fixed sentence. Overriding it with fixed text removed that call.

Mid-flow and chitchat moved within noise (mid-flow ranged 3976–5368ms across rounds), so the
Haiku rephraser swap and the `max_tokens` reduction are **not** independently evidenced as wins.

**Remaining floor: ~4s is the single Claude command-generation call.** The only lever that
moves it meaningfully is running command generation on Haiku, untested for accuracy and
deliberately not attempted before the demo.

**Cold start is ~12.5s.** Send a throwaway message before demoing.

The ~200× gap between the engines quantifies what the LLM buys (flexible language
understanding) against what it costs (latency).

---

## Caveats

- Latency figures are single-machine, single-run on a developer laptop, not a benchmark, and
  vary with network conditions to the Anthropic API.
- Neither suite checks reply *wording* or tone. The policy-figure errors corrected on
  2026-08-09 were found by reading the source policy document against the code; the
  condolences-on-a-policy-question defect was found by a human reading a suggestion chip.
  Both would have passed every automated check at the time.
