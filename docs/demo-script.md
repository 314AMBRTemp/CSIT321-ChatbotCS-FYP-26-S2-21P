# AskIvy HRMS — Demo Script

Roughly 12–15 minutes. Each section says what to do, what to say, and what should happen.

---

## 0. Before anyone is watching

| Step | Why |
|---|---|
| Run `run-askivy.bat`, wait for all four windows | The Rasa server takes ~30s to load its model |
| Open `http://localhost:5000/api/askivy/rasa/health` — expect `"status":"ok"` | Confirms Rasa is up and which model is loaded |
| Send one throwaway message in the widget | **Cold start is ~12.5s.** Warm it up or your first live answer looks broken |
| Log out | So you can start on the login screen |

Have the deployed site open in a second tab:
`https://csit321-chatbotcs-fyp-26-s2-21p-1.onrender.com` — used in section 9.

---

## 1. The login screen

Employees are grouped by department, HR first. Point out **Nadia Rahman** carries a
*Support* badge — used at the end.

Log in as **Sarah Tan** (Principal Engineer, Engineering, 7 years).

> "Everything AskIvy says about Sarah comes from her real HRMS record, not from the model's
> memory."

---

## 2. A grounded answer

Open AskIvy, ask:

```text
How many leave days do I have?
```

**Expect:** her real balance out of her 21-day entitlement, plus sick leave, and a
`§ Annual Leave | Sick Leave` citation under the reply.

> "The number is read from the database and the policy is named underneath. It isn't
> recalled — it's retrieved."

Expand the reasoning trace and show the Understand → Retrieve → Compute → Answer steps.

---

## 3. Guided interaction — buttons

```text
I want to apply for leave
```

**Expect:** four buttons — Annual, Sick, Compassionate, Parental. Click **Annual**.
Note the transcript shows "Annual", not the underlying payload.

Answer `2 days`, then use the **Yes, submit it** button.

> "The assistant guides the choice instead of hoping the employee phrases it correctly.
> Typing 'annual' works identically — the buttons are an affordance, not a constraint."

---

## 4. A real HRMS transaction, and undoing it

Go to the **Leave** page. The request is there, `Pending`, `submittedVia: AskIvy`, and the
balance has dropped.

> "The chatbot didn't describe an action. It performed one."

Now back to AskIvy:

```text
Cancel my pending leave request
```

**Expect:** Yes/No buttons. Confirm. Return to the Leave page — status `Cancelled`, balance
restored.

> "Cancelling restores the balance because this prototype deducts at submission. A
> production HRMS would deduct on approval — we scoped to pending-only deliberately."

---

## 5. The same question, two different people

```text
Am I eligible for parental leave?
```

Sarah (7 years, Principal) → **eligible**, plus the extra 2 weeks of flexible return-to-work
leave for Principal / Lead / Head-of-Department level.

Now sign out, log in as **Marcus Reyes** (Junior Designer, 0 years, probation) and ask the
same thing.

**Expect:** not eligible, his actual tenure quoted back, and an HR contact with context —
*"mention you're asking about parental leave with 0 year(s) of service."*

> "Same question, same policy, different answer — because it reasons over the employee's
> record. And when it can't help, it hands off with enough context that the employee doesn't
> have to re-explain themselves."

---

## 6. A sensitive case

Still as Marcus:

```text
My mother passed away last night
```

**Expect:** condolences, immediate-family classification, **5 days**, and an offer to file it.

Then, to show the distinction:

```text
What is the compassionate leave policy?
```

**Expect:** the policy text and **no condolences** — it recognises a policy lookup rather
than a bereavement.

> "Someone reading up on entitlements shouldn't be told we're sorry for their loss. That
> distinction is a regression test, not an accident."

---

## 7. Where it says no — the most important section

Log in as **Siti Rahman** (Operations Executive).

```text
I want to move into Sales, what do I need to do?
```

**Expect:** certifications and steps from the career library, **plus** the Internal Transfer
requirements — 12 months in role, dual endorsement, 2–4 week handover — then Yes/No buttons
offering to raise it with HR.

Now ask for something that doesn't exist:

```text
What would it take to move into Marketing?
```

**Expect:** *"I don't have a specific plan yet"*, the paths that **do** exist from Operations,
and an HR handoff naming her department and target.

> "This is the design principle: every answer traces to a policy or a record. When there's
> nothing to cite, it says so instead of inventing a plausible career plan. An assistant that
> improvises HR advice is worse than no assistant."

---

## 8. Off-topic

```text
What's the weather like today?
```

**Expect:** a natural, in-character reply that redirects to HR topics — no invented facts,
no `placeholder`.

---

## 9. Two engines, one contract

Switch to the deployed tab and ask it the same leave-balance question.

> "Same interface, same response shape — but this one is the rule-based engine, no LLM. The
> chatbot layer is swappable behind one contract, which is how we can compare them directly.
> Rule-based answers in about 40 milliseconds; the LLM takes about four seconds and handles
> phrasing the rules never anticipated."

---

## 10. The support view

Sign out, log in as **Nadia Rahman** (Human Resources, *Support* badge). A **Support** tab
appears that other employees don't see.

Open it: every conversation across the organisation, filterable by employee.

> "HR can see what people are actually asking — which is how you find the questions the
> assistant handles badly, and the gaps in policy communication."

Filter to one employee to show it working.

---

## 11. Architecture

> "HR policies live in a document repository; employee records and leave transactions live in
> the database. AskIvy sits between them. Rasa CALM manages the conversation — which flow,
> which slots — and Claude does the language understanding. The custom actions never touch
> the database directly; they call the same REST API the web UI uses, so leave accounting has
> exactly one implementation."

If asked about testing: two suites. The Rasa e2e suite proves flows route correctly against
live Claude calls; a separate API-level suite proves the answers are factually right against
real employee records. `docs/test-results/README.md` explains why both are needed.

---

## If something breaks

| Symptom | Cause |
|---|---|
| First answer takes ~12s | Cold start — should have been warmed up in section 0 |
| "I can't reach the HRMS right now" | Flask (`:5000`) is down |
| "can't reach AskIvy's reasoning service" | Rasa (`:5005`) is down |
| Bot resumes an old half-finished flow | Sign out and back in — that resets the tracker |
| Edited a file and nothing changed | `actions.py` needs an action-server restart; `domain.yml` / `flows.yml` need `retrain-askivy.bat` |
