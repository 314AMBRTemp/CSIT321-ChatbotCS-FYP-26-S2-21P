# AskIvy — User Stories

Sections 3.1–3.5. The 3.1 rows were marked **YHF** in the original; the rest had no owner set.
Wording unchanged; only the grouping is new. Status assessed **2026-08-10** against the build.

Sorted by status rather than by section. Every row keeps its original `3.x.n` ID, so it still
maps back to the report's numbering.

> **Design note carried over from the original, on 3.3:** unlike a live IT-helpdesk-style queue,
> there is no real-time escalation channel behind the chatbot. When a question is beyond its
> scope, it simply refers the employee to the HR Dept through normal channels.

**Legend:** ✅ done · ⚠️ partial · ❌ not started
**Score:** 6 done · 7 partial · 13 not started (26 total)

---

## ✅ Done (6)

| ID | Role | Title | Story | What implements it |
|---|---|---|---|---|
| 3.1.1 | Employee | Ask Questions / Get Assistance | Ask the chatbot about HR policies, to find information without contacting HR directly. | `policy_question` flow → `action_policy_answer`, cites real text from `hr_policies.json` |
| 3.1.2 | Employee | Leave Balance Check | Check leave balance through the chatbot, without opening a separate page. | `check_leave_balance` flow, reads the live HRMS record |
| 3.1.3 | Employee | Leave Application | Apply for leave through the chatbot, without filling out a separate form. | `apply_for_leave` flow — actually writes a `Pending` row to the database |
| 3.1.7 | Employee | Display HR Policy Source | See the policy section used to answer, to verify the information. | `source` field rendered as `§ {source}` in `ChatWidget` |
| 3.1.9 | Employee | Chatbot Confidence | Be told when the bot can't confidently answer, so I know to ask HR. | Honest fallbacks throughout: career "no plan yet", `API_DOWN_MESSAGE`, chitchat deflection |
| 3.3.1 | Employee | Clear Referral When Unresolved | Be told clearly when the bot can't help, so I contact HR instead. | Career no-match branch, policy fallbacks, chitchat redirect |

---

## ⚠️ Partial (7)

| ID | Role | Title | Story | What's there / what's missing |
|---|---|---|---|---|
| 3.1.5 | Employee | Conversation History | View previous conversations, to refer back to earlier answers. | **Stored** — both engines write `ChatMessage` (`app.py:164`, `rasa_adapter.py:136`). **Missing:** no GET route, no UI. Widget clears on employee switch. |
| 3.1.8 | Employee | Restart Conversation | Clear the current conversation to start fresh. | `POST /api/askivy/rasa/reset` works. **Missing:** no button in the widget. |
| 3.2.3 | Employee | Submission Confirmation | Get confirmation after submitting, as proof it was received. | Leave submit and cancel both confirm clearly. **Missing:** no *case* concept to confirm. |
| 3.3.3 | Administrator | Track Unanswered Questions | See which questions the bot couldn't answer, to improve content. | All exchanges logged including fallbacks. **Missing:** no "unanswered" flag, no report, no view. |
| 3.4.2 | Administrator | Manage Policy Topics | Organise content by policy topic so updates stay isolated. | Policies already carry a `category` and are separate objects. **Missing:** any management UI — edits are hand-edited JSON. |
| 3.5.1 | Employee | Response Feedback | Give thumbs up/down on responses. | CALM's `pattern_customer_satisfaction` **already renders 👍/👎 buttons**. **Missing:** it's per-conversation not per-response, and the score lands in the Rasa tracker, not our DB. |
| 3.5.4 | IT Admin | View Conversation Log | View logs to troubleshoot and audit. | Same data as 3.1.5 — fully captured. **Missing:** no route, no view, no auth to gate it behind. |

---

## ❌ Not started (13)

| ID | Role | Title | Story | Blocker / note |
|---|---|---|---|---|
| 3.1.4 | Employee | Session Timeout Warning | Warn before the chat session times out. | No session-timeout concept exists anywhere |
| 3.1.6 | Employee | Suggested Follow-up Questions | Suggest related questions **after** an answer. | Starter chips exist, but only on the *empty* state — wrong moment |
| 3.2.1 | Employee | Grievance Submission | Submit a grievance so it's recorded and routed to HR. | No case/grievance model at all |
| 3.2.2 | Employee | Case Follow-up | Check the status of a submitted case. | Depends on 3.2.1 |
| 3.2.4 | HR Dept | View Assigned Case | View cases escalated by the chatbot. | **No HR role or login exists** |
| 3.2.5 | HR Dept | Update Case Status | Update a case so the employee sees progress. | **No HR role or login exists** |
| 3.3.2 | Employee | HR Contact Details | Share HR's email when referring me. | Nothing anywhere holds an HR contact address — **cheapest fix in the whole list** |
| 3.4.1 | Administrator | Manage Chatbot Responses | Create and update the bot's answers. | **No admin role or UI** — editing means hand-editing JSON/YAML |
| 3.4.3 | Administrator | Manage FAQ Library | Maintain an FAQ library for consistent answers. | **No admin role or UI** |
| 3.4.4 | Administrator | Review Usage Analytics | See most-asked topics to spot policy gaps. | **No admin role or UI.** Underlying data partly exists in `chat_messages` |
| 3.4.5 | IT Admin | Manage Access & Permissions | Control who can edit content or view employee data. | **No authentication of any kind** — login is click-to-pick-employee, no password |
| 3.5.2 | Administrator | Review Feedback | Review feedback to improve weak answers. | **No admin role or UI**; depends on 3.5.1 persisting scores |
| 3.5.3 | Administrator | Preview Before Publish | Preview response changes before publishing. | **No admin role or UI**; depends on 3.4.1 |

---

## The gap is one thing, not thirteen

**11 of the 13 unbuilt stories are Administrator, HR Dept, or IT Admin stories**, and the app
has **no authentication and no roles at all**. All of 3.4, both HR-side 3.2 stories, and two
of 3.5 sit behind that single absence. It's one architectural decision, not thirteen features.

The two that aren't role-blocked — 3.1.4 (session timeout) and 3.1.6 (follow-up suggestions) —
are both small and independent.

---

## Built, but no story covers it

Scope drift, in the direction of good features. Reconcile before submission — either write
stories for these or note the deviation deliberately.

| Feature | Where |
|---|---|
| Cancel a pending leave request | `cancel_leave` flow + `POST /api/employees/<id>/leave/<id>/cancel` + Cancel button in the Leave table |
| Career path advice | `career_path_advice` flow, full 20-pair matrix in `career_paths.json` |
| Internal Transfer eligibility citation | `TRANSFER-01` cited on both branches of the career flow |
| Ask-HR follow-up after career advice | `confirm_flag_hr` collect step |
| Compassionate leave with relationship classification | `compassionate_leave` flow (immediate 5 days / extended 3 days) |
| Parental leave eligibility | `parental_eligibility` flow, incl. the senior top-up |
| Freeform chitchat | `pattern_chitchat` → `action_free_chitchat` |
| Two interchangeable chat engines | rule-based + Rasa/Claude behind one response contract |

---

## Cheapest wins

1. **3.3.2 HR contact email** — one line. The bot already refers to HR, it just never says how to reach them.
2. **3.1.8 Reset button** — the API route already exists and works.
3. **3.1.5 + 3.3.3 + 3.5.4** — one `GET /api/employees/<id>/chat` route plus a simple view converts **three** partials. The hard part (capturing the data) is already done by both engines.
4. **3.5.1 Persist the CSAT score** — turns an accidental partial into a met story.

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
