# AskIvy — User Stories

Sections 3.1–3.5. The 3.1 rows were marked **YHF** in the original; the rest had no owner set.
Wording unchanged; only the grouping is new. Status assessed **2026-08-10**, refreshed
**2026-08-11** after landing 3.1.6, 3.2.2, and 3.2.5.

Sorted by status rather than by section. Every row keeps its original `3.x.n` ID, so it still
maps back to the report's numbering.

> **Design note carried over from the original, on 3.3:** unlike a live IT-helpdesk-style queue,
> there is no real-time escalation channel behind the chatbot. When a question is beyond its
> scope, it simply refers the employee to the HR Dept through normal channels.

**Legend:** ✅ done · ⚠️ partial · ❌ not started
**Score:** 19 done · 4 partial · 3 not started (26 total)

---

## ✅ Done (19)

| ID | Role | Title | Story | What implements it |
|---|---|---|---|---|
| 3.1.1 | Employee | Ask Questions / Get Assistance | Ask the chatbot about HR policies, to find information without contacting HR directly. | `policy_question` flow → `action_policy_answer` → shared `build_policy_answer()`. Now three layers: a general summary (generated, cached), a line tailored to the employee's own record, then the policy's rules quoted verbatim. |
| 3.1.2 | Employee | Leave Balance Check | Check leave balance through the chatbot, without opening a separate page. | `check_leave_balance` flow, reads the live HRMS record |
| 3.1.3 | Employee | Leave Application | Apply for leave through the chatbot, without filling out a separate form. | `apply_for_leave` flow — actually writes a `Pending` row to the database |
| 3.1.4 | Employee | Session Timeout Warning | Warn before the chat session times out. | No real server session to expire (the Rasa tracker persists indefinitely), so this is a frontend idle clock over the open widget: a banner at 4 minutes idle, an actual reset (transcript cleared, Rasa tracker reset) at 5 — see `ChatWidget.jsx`. |
| 3.1.5 | Employee | Conversation History | View previous conversations, to refer back to earlier answers. | `GET /api/employees/<id>/chat` + the **History** page in the app nav, listing every past exchange newest-first |
| 3.1.6 | Employee | Suggested Follow-up Questions | Suggest related questions **after** an answer. | The policy scorer already ranks the next-closest matches to every question asked; `build_policy_answer()` now surfaces those as `relatedPolicies` instead of discarding them. Rendered as clickable chips ("What about Parental Leave?") under the reply, on both engines. No LLM call, no new computation — reused what `search_policies()` already returned. |
| 3.1.7 | Employee | Display HR Policy Source | See the policy section used to answer, to verify the information. | `source` field rendered as `§ {source}` in `ChatWidget`; now backed by the database-mirrored policy table rather than the raw JSON file |
| 3.1.9 | Employee | Chatbot Confidence | Be told when the bot can't confidently answer, so I know to ask HR. | Honest fallbacks throughout: career "no plan yet", `API_DOWN_MESSAGE`, chitchat deflection |
| 3.2.2 | Employee | Case Follow-up | Check the status of a submitted case. | `GET /api/employees/<id>/hr-requests` — no admin gate, it's the employee's own data, same pattern as `/leave` and `/chat`. Rendered as a **My HR requests** section on the History page, hidden entirely when empty rather than showing a permanent zero-row table to employees who've never raised anything. |
| 3.2.4 | HR Dept | View Assigned Case | View cases escalated by the chatbot. | The Support tab's HR Requests table now has an **Assigned to** column. Every request auto-assigns to the support/HR account at creation (`assigned_to` on `HRRequest`) — honest for this demo's one working HR persona; a real multi-person HR team would need a real claim/reassign step. |
| 3.2.5 | HR Dept | Update Case Status | Update a case so the employee sees progress. | `PATCH /api/admin/hr-requests/<id>`, admin-gated, validated against `Open → In Progress → Closed`. Rendered as an editable dropdown styled as the existing status pill in the Support table. The employee-facing 3.2.2 view reflects it immediately — same row, same `status` field, no separate sync needed. |
| 3.3.1 | Employee | Clear Referral When Unresolved | Be told clearly when the bot can't help, so I contact HR instead. | Career no-match branch, policy fallbacks, chitchat redirect |
| 3.3.2 | Employee | HR Contact Details | Share HR's email when referring me. | `HR_CONTACT_EMAIL` is included in every HR handoff (`_hr_handoff()`) and in `API_DOWN_MESSAGE` |
| 3.3.3 | Administrator | Track Unanswered Questions | See which questions the bot couldn't answer, to improve content. | `ChatMessage.unanswered`, set explicitly (never inferred from text) at genuine "couldn't answer" branches in both engines — HRMS/career-library unreachable, no career path on file for the pair. NOT set for a fuzzy policy match or a chitchat deflection; those are complete, honest answers. Support tab has a "Show only unanswered" filter and an analytics count. |
| 3.4.2 | Administrator | Manage Policy Topics | Organise content by policy topic so updates stay isolated. | Full admin CRUD in the Support tab (`/api/admin/policies`) — list, create, edit, delete, backed by the already-DB-resident `Policy` rows. Landing this is also why `seed_policies()` had to switch from re-syncing every boot to seeding once: editable rows can't be silently overwritten by the file on the next restart. |
| 3.4.3 | Administrator | Manage FAQ Library | Maintain an FAQ library for consistent answers. | **Scope decision:** no second content store. An FAQ entry is just a `Policy` row with a freeform `category` (e.g. "Workplace") added through the same 3.4.2 editor. A parallel FAQ table would let the same question have two different stored answers depending which table served it — exactly the drift this whole session has been removing, not adding back. |
| 3.4.4 | Administrator | Review Usage Analytics | See most-asked topics to spot policy gaps. | `GET /api/admin/analytics` aggregates data that already existed: most-cited policy topics (from `chat_messages.policy_used`), HR requests by topic, unanswered rate, feedback split. Rendered as stat cards + two tables in the Support tab. |
| 3.5.1 | Employee | Response Feedback | Give thumbs up/down on responses. | Persisted per-message now, not per-conversation: `ChatMessage.feedback` (`"up"`/`"down"`/`null`), set via `POST /api/chat-messages/<id>/feedback`. Thumbs render under every bot reply in `ChatWidget` (not just the newest), and the transcript shows a 👍/👎 badge per entry. Superseded CALM's `pattern_customer_satisfaction`, which only rated a whole conversation and stored the score in the Rasa tracker, not the app's own database. |
| 3.5.4 | IT Admin | View Conversation Log | View logs to troubleshoot and audit. | `GET /api/admin/chats`, gated 403 to `isAdmin` accounts, rendered as the **Support** tab's transcript view |

---

## ⚠️ Partial (4)

| ID | Role | Title | Story | What's there / what's missing |
|---|---|---|---|---|
| 3.1.8 | Employee | Restart Conversation | Clear the current conversation to start fresh. | `POST /api/askivy/rasa/reset` works and fires automatically on employee switch, and (new) the 3.1.4 idle timer resets it too. **Missing:** still no button the employee can press mid-conversation on demand. |
| 3.2.1 | Employee | Grievance Submission | Submit a grievance so it's recorded and routed to HR. | `POST /api/hr-requests` persists a row (topic, question, situation, manager copied, now also assigned) and support sees it in the **HR Requests** table. **Missing:** it's reachable only as an offer *after* a policy answer, not a general "I want to raise something" entry point — and it isn't scoped for grievances specifically (conduct complaints, disputes). |
| 3.2.3 | Employee | Submission Confirmation | Get confirmation after submitting, as proof it was received. | Leave submit/cancel and HR requests all confirm clearly. **Missing:** no *case* concept spanning them — each confirms independently. |
| 3.5.2 | Administrator | Review Feedback | Review feedback to improve weak answers. | *(Upgraded from not-started — a side effect of 3.5.1, not separately built.)* Every transcript entry in the Support tab now shows its 👍/👎, and the analytics section totals them. An admin can browse and spot a downvoted reply in context today. **Missing:** no "show only downvoted" filter (the 3.3.3 unanswered filter is the template for it), and no workflow around what happens after spotting one — it's browsable, not yet a queue. |

---

## ❌ Not started (3)

| ID | Role | Title | Story | Blocker / note |
|---|---|---|---|---|
| 3.4.1 | Administrator | Manage Chatbot Responses | Create and update the bot's answers. | Different from 3.4.2/3.4.3 (now done) on purpose — this means the bot's own utterances and flow structure (`domain.yml`, `flows.yml`), not HR policy content. Those live in YAML and need a retrain to take effect, a fundamentally different mechanism from editing a database row live. **Deliberately parked — see below**, not blocked on anything technical. |
| 3.4.5 | IT Admin | Manage Access & Permissions | Control who can edit content or view employee data. | **No real authentication** — login is click-to-pick-employee, no password. This is the one story still blocked at the architecture level, not just missing a screen. The new `/api/admin/policies` write endpoints inherit this: they're gated by the same spoofable `?requesterId=` check as everything else under `/api/admin/*`. |
| 3.5.3 | Administrator | Preview Before Publish | Preview response changes before publishing. | No admin UI; depends on 3.4.1 |

---

## The gap is smaller than it looks, and it's two different gaps

The previous version of this file said the whole remaining gap was "no authentication and no
roles at all." That's no longer accurate — **an admin role now genuinely exists**: `Employee.is_admin`,
enforced 403 on `/api/admin/chats` and `/api/admin/hr-requests`, and a working Support tab that
uses it. Nadia Rahman's account demonstrates it end-to-end.

What's actually left splits into two different problems:

1. **Missing screens, not missing architecture.** This was true of 3.4.2/3.4.3/3.4.4 and 3.2.5,
   and all four are now done — CRUD UI built directly on the admin role and the `HRRequest`
   table that already existed, no new architecture needed. 3.5.3 is the same shape, just not
   built yet.
2. **Missing real authentication.** Only 3.4.5 is blocked at the architecture level. "Login" is
   still click-to-select-an-employee — fine for a demo, not a permissions boundary. Adding
   password auth is the one piece that would need a design decision, not just screen time.

**3.4.1 is neither of these — it's its own architectural fork, deliberately parked rather than
built.** Every story landed so far edits a live database row. 3.4.1 means editing the bot's own
`domain.yml`/`flows.yml` responses, which Rasa bakes into the trained model at `rasa train`
time — there's no live-edit path without a real design decision first: hand-edit-YAML-then-
retrain (slow, only reaches the Rasa engine, not the rule-based one the deployed site actually
runs), or migrate the editable responses into a DB-backed custom NLG endpoint (more work, but
consistent with how 3.4.2 already works and reaches both engines). Worth deciding deliberately,
not guessing at.

---

## An inconsistency worth fixing before submission

There are now **two different "flag this to HR" mechanisms** and they don't behave the same way:

- The **career path flow**'s `confirm_flag_hr` step (`rasa/data/flows.yml`) only utters
  `utter_hr_flagged` — nothing is written anywhere. If HR never happens to see that chat log,
  the flag is lost.
- The **policy answer**'s "Yes, raise it" offer calls `POST /api/hr-requests`, which persists a
  row support can actually see and act on.

Same user intent ("please tell HR"), two different outcomes depending on which flow triggered
it. Worth deciding whether the career flow should also write an `HRRequest` row — it's a small
change now that the endpoint exists — or whether the difference is intentional and worth a
one-line comment explaining why.

---

## Built, but no story covers it

Scope drift, in the direction of good features. Reconcile before submission — either write
stories for these or note the deviation deliberately.

| Feature | Where |
|---|---|
| Cancel a pending leave request | `cancel_leave` flow + `POST /api/employees/<id>/leave/<id>/cancel` + Cancel button in the Leave table |
| Career path advice | `career_path_advice` flow, full 20-pair matrix in `career_paths.json` |
| Internal Transfer eligibility citation | `TRANSFER-01` cited on both branches of the career flow |
| Compassionate leave with relationship classification | `compassionate_leave` flow (immediate 5 days / extended 3 days) |
| Parental leave eligibility | `parental_eligibility` flow, incl. the senior top-up |
| Freeform chitchat | `pattern_chitchat` → `action_free_chitchat` |
| Two interchangeable chat engines | rule-based + Rasa/Claude behind one response contract |
| Tailored, generated policy explanations | `policy_explainer.py` + `policy_situation.py` — a general summary is generated and cached per policy; eligibility is computed from the employee's own record, never guessed by the model |
| Manager lookup for HR handoffs | `Employee.manager_name/manager_email`, seeded from department heads, used to "cc your manager" on an HR request |

---

## Cheapest wins, updated

3.3.2, 3.1.5/3.5.4, 3.1.4/3.2.4/3.3.3/3.4.2/3.4.3/3.4.4/3.5.1, and now 3.1.6/3.2.2/3.2.5 are all
done. What's actually cheap from here:

1. **3.1.8 Reset button** — the API route already exists and works, and now so does the 3.1.4
   idle timer's reset path; just needs a button in the widget for on-demand use too.
2. **The HR-request inconsistency below** — routing `confirm_flag_hr` through
   `POST /api/hr-requests` is a small, contained fix with an outsized correctness payoff.
3. **A "show only downvoted" filter for 3.5.2** — identical shape to the 3.3.3 unanswered
   filter, and now also to the 3.2.2 pattern of "show only mine"; would turn 3.5.2 from
   browsable into an actual review queue.

---

## Still open from before

- **CSAT — resolved, not built.** Decided not to build a separate whole-conversation
  satisfaction score. The gap it would have closed — measuring satisfaction from people who
  never explicitly decline the "anything else?" prompt — is already covered by what 3.5.1 and
  3.3.3 capture passively: per-message thumbs need no prompt at all, and the unanswered rate is
  itself a negative signal that needs no one to volunteer it. A dedicated CSAT score would
  duplicate that without adding new information, so it's parked rather than half-built. CALM's
  own `pattern_customer_satisfaction` is untouched and still only lives in the Rasa tracker if
  it ever fires — that's fine, since nothing here depends on it anymore.
- **Policy corpus coverage** — roughly 10 of ~20 real HR areas are represented (Exam Leave,
  Training & Development, Equipment, Disciplinary & Grievance, Business Travel, etc. are still
  missing). Adding them is now a 3.4.2 admin-UI job, not a `hr_policies.json` edit — **the file
  stopped being the live source** the moment `seed_policies()` switched to seed-once for the
  policy editor (see 3.4.2 above). Worth doing before analytics (3.4.4) would have anything
  meaningful to show for those topics.

---

# [Ideas] — Live web lookup (opening)

Captured 2026-08-10. Not ratified — candidate stories and design notes for letting AskIvy pull
in current, real-world information, kept here so the idea isn't lost.

## The idea

Some answers go stale in a curated file and shouldn't live in one. `career_paths.json` already
tells an employee they need a "Certified Sales Professional (CSP)" — but not who offers it, what
it costs now, or when the next intake is. A live lookup covers that without anyone maintaining a
providers dataset.

## How (no Google scraping)

The Anthropic Messages API has a **built-in server-side `web_search` tool**. Claude issues the
query, Anthropic runs the search, results come back as content blocks in the same response. No
scraping, no Google API key, no ToS problem. Scraping Google directly was the original thought
and is a dead end: against their ToS, blocked by bot detection, and the official Custom Search
JSON API is capped at 100 queries/day and needs a key plus a Search Engine ID.

`actions.py` already calls the Messages API directly via `requests`, so enabling it is roughly
adding a `tools` key to the existing call.

## Design decisions to carry forward

- **Build it as a shared capability, not a chitchat feature.** If search serves career paths
  *and* wellbeing *and* off-topic chat, it belongs beside `_ask_claude()` as a helper any action
  can call — cheap now, annoying to retrofit later.
- **Keep grounded and searched sources visually separate in the reply.** The strength of this
  project is that every HR claim traces to a policy or an HRMS record. Blending "the policy
  requires 12 months in role" with "here's a bootcamp I found" into one paragraph weakens that.
  Policy first, then "publicly available options I found".
- **Model constraint.** The newer `web_search_20260209` (dynamic filtering) needs Opus 4.6+ /
  Sonnet 4.6+. Chitchat runs on Haiku 4.5 for speed, so it would use the basic
  `web_search_20250305` variant.
- **Latency and cost.** A search round-trip adds meaningfully to response time, right after a
  session spent reducing it. Web search is also billed per search on top of tokens. Scope with
  `max_uses` and a prompt rule to only search when the question genuinely needs current
  information — otherwise every "how are you?" pays for a search.
- **Errors don't raise.** A failed search returns HTTP 200 with an error object inside the result
  block, not an exception. The existing fallback in `_ask_claude()` degrades safely.
- **Medical is a different risk class.** Certification providers are low-stakes; naming specific
  hospitals to an employee is not. Suggested scope: answer "what your coverage includes and who to
  contact" and leave provider choice to the employee.

## Candidate user stories

| # | Role | Title | Story | Source of answer |
|---|---|---|---|---|
| I1 | Employee | Find certification providers | Know where I can actually take the certifications my career path recommends, to budget and schedule before committing. | Grounded (cert names from `career_paths.json`) + searched (providers, cost, intake) |
| I2 | Employee | Check certification currency | Know whether a recommended certification is still current or superseded, so I don't pay for an outdated qualification. | Searched |
| I3 | Employee | Understand transfer prerequisites | See the real-world prerequisites for a target role, to tell how far off I am. | Grounded (`TRANSFER-01`) + searched |
| I4 | Employee | Medical coverage guidance | Know what my medical coverage includes and who to contact, to act without guessing. | Grounded only — deliberately **not** searched; the bot must not select providers |
| I5 | Employee | Wellbeing signposting | Be pointed to the EAP or support services the company actually offers. | Grounded (policy repository) |
| I6 | Employee | Plan time off | Get general suggestions for the period I'm away, after booking annual leave. | Searched — explicitly labelled general info, not HR advice |
| I7 | Employee | Trust the source | See which parts of an answer come from company policy and which from a public search. | Cross-cutting requirement on every searched answer |
| I8 | Administrator | Control what gets searched | Control which topics the bot may search the web for, so it never improvises on sensitive matters. | Config |

## Open questions

- Which flows get search: career/transfer only, or leave and policy too?
- Per-flow opt-in, or one global capability with a topic blocklist?
- Is the added latency acceptable on the career path flow, already the slowest?
- Does a searched answer get logged differently from a grounded one, for auditability?

# [Ideas] — closing

Nothing in this section is built. It is scoped, not committed. The nearest concrete step is **I1**
— it attaches to an existing, working flow (`career_path_advice`), uses data the flow already has,
and is the clearest demonstration of grounded-plus-live in one answer.

Note that **I8 depends on the same missing admin layer** that blocks 3.4 above — so it can't land
before authentication exists.
