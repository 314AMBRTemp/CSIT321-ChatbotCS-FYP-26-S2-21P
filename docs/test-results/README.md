# Test & Measurement Evidence

Generated artifacts from validation runs. Regenerate with:

```powershell
cd rasa
.venv\Scripts\activate
rasa test e2e tests/e2e_test_cases.yml -o ../docs/test-results/e2e-results.yml --coverage-report --coverage-output-path ../docs/test-results/coverage
```

Requires Flask (`:5000`) and the action server (`:5055`) running — the custom actions call
the live REST API, so this exercises the real stack, not mocks.

---

## End-to-end tests — 2026-08-10

**14 / 14 passed. 100% on every assertion type.**

| Assertion type | Accuracy |
|---|---|
| `flow_started` | 100.00% |
| `action_executed` | 100.00% |
| `slot_was_set` | 100.00% |
| `bot_uttered` | 100.00% |

Model under test: `20260810-152731-taxonomic-poset.tar.gz`

Every case runs against **live Claude output** — the command generator makes a real
Anthropic API call per turn. These are not recorded fixtures.

### Flow coverage — 86.96% (20 of 23 steps)

| Flow | Coverage | Steps | Missing |
|---|---|---|---|
| check leave balance | 100% | 1 | — |
| apply for leave | 100% | 5 | — |
| compassionate leave | 100% | 2 | — |
| parental eligibility | 100% | 1 | — |
| policy question | 100% | 2 | — |
| career path advice | 100% | 5 | — |
| **cancel leave** | **57.14%** | 7 | **3** (`flows.yml` 91-92, 94-95, 102-105) |
| **Total** | **86.96%** | 23 | 3 |

**The one real gap is `cancel_leave`.** Its three branches are covered unevenly: the
one-pending-request path is tested, but the **zero-pending** branch (`utter_no_pending_leave`)
and the **multiple-pending** branch (the `leave_to_cancel` disambiguation collect) are not.

Both are awkward to test because they depend on database state — the seed data gives exactly
one employee a single pending request, and cancelling it in a test mutates that state for the
next run. Covering them properly needs either a seeded fixture employee with two pending
requests, or a reset step before the suite. Worth doing; not done.

### Files

| File | What it is |
|---|---|
| `e2e-results_passed.yml` | Full transcript of each passing case |
| `e2e-results_failed.yml` | Empty — no failures |
| `coverage/coverage_report_for_passed_tests.csv` | Per-flow coverage, source of the table above |
| `coverage/commands_histogram_for_passed_tests.png` | Distribution of commands Claude generated (`StartFlow`, `SetSlot`, `ChitChat`, …) |
| `coverage/passed/e2e_test_cases.yml` | The cases that passed, as executed |

---

## Latency — 2026-08-10

Measured warm (first call after a restart discarded), 3 rounds, via `/api/askivy/chat-rasa`.

| Interaction | Before | After | LLM calls after |
|---|---|---|---|
| Completed flow (e.g. leave balance) | ~8.3s | **~6.0s** | 2 |
| Mid-flow question | ~3.6s | ~4.5s | 1 |
| Chitchat | ~5.1s | ~4.8s | 2 |
| Rule-based engine, same question | — | **37ms** | 0 |

**What produced the gain:** `utter_ask_continue_conversation` — the "anything else?" tail on
every completed flow — was being rewritten by the NLG rephraser, costing a full extra LLM
round trip to reword one fixed sentence. Overriding it with fixed text removed that call.

Mid-flow and chitchat moved within noise (mid-flow ranged 3976–5368ms across rounds), so the
Haiku rephraser swap and the `max_tokens` reduction are not independently evidenced as wins.

**Remaining floor: ~4s is the single Claude command-generation call.** The only lever that
moves it meaningfully is running command generation on Haiku, which is untested for accuracy
and was deliberately not attempted before the demo.

**Cold start is ~12.5s** — the first request after a restart. Send a throwaway message before
demoing.

The ~200× gap between the two engines is a genuine finding for the report: it quantifies what
the LLM buys (flexible language understanding) against what it costs (latency).

---

## Caveats

- Both numbers above are single-machine, single-run measurements on a developer laptop, not
  a benchmark. Latency in particular varies with network conditions to the Anthropic API.
- The e2e suite asserts on **flows, slots, and actions** — not on reply wording. It will not
  catch a reply that is worded badly or cites a wrong figure, only one that routes wrongly.
  The policy-figure corrections on 2026-08-09 were found by reading the source document
  against the code, not by these tests.
