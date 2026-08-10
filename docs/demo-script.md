# AskIvy HRMS Demo Script

## 1. Start the system

Run the Flask backend and React frontend.

Backend:

```bash
cd backend
python app.py
```

Frontend:

```bash
cd frontend
npm run dev
```

## 2. Login as Sarah

Show that Sarah is a confirmed employee with 7 years of service. Explain that this profile is stored in the database and used by AskIvy for personalised answers.

## 3. Ask a personalised policy question

Ask:

```text
Am I eligible for parental leave?
```

Expected explanation:

- AskIvy retrieves the Parental Leave policy.
- It checks Sarah's tenure from the database.
- It gives a personalised answer.

## 4. Ask a recommendation-style question

Ask:

```text
I need to take compassionate leave
```

Expected explanation:

- AskIvy recognises bereavement.
- It retrieves Compassionate Leave.
- It understands that cousin is extended family.
- It recommends up to 3 paid working days, subject to approval.
- It prepares a leave request action.

## 5. Submit through AskIvy

Click **Submit this request**.

Then go to the Leave page and show the pending leave request. Explain that this proves the chatbot is not only answering; it can trigger a backend HRMS transaction.

## 6. Login as Marcus

Ask the same parental leave question. Show that Marcus receives a different answer because he is still in probation and has under 1 year of service.

## 7. Explain the architecture

Use this line:

> HR policies are maintained in a document repository, while employee records and leave transactions are stored in the database. AskIvy sits between both sources and acts as the intelligent layer that retrieves, checks, reasons, and recommends the best HR action.
