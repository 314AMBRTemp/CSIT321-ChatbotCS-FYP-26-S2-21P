# AskIvy HRMS Architecture

## Proposed real-life stack

| Layer | Recommended Technology | Purpose |
|---|---|---|
| Frontend | React.js | HRMS portal, chatbot widget, employee self-service UI |
| Backend | Python Flask REST API | Business logic, API endpoints, AskIvy processing, leave submission |
| Database | PostgreSQL | Employee records, leave balances, leave requests, chat history |
| Policy Repository | Document repository / HR knowledge base | HR policy documents and source content |
| AI Layer | Retrieval + reasoning service | Understand question, retrieve policy, check profile, recommend action |

## Why React?

React is suitable because the HRMS has repeated interface sections such as dashboard cards, policy cards, leave tables, forms, and the AskIvy chatbot widget. React allows these sections to be separated into reusable components, making the frontend easier to maintain and troubleshoot.

## Why Flask?

Flask is suitable for the FYP because it is lightweight and easy to explain. It can expose REST API endpoints for employee data, leave requests, policies, and AskIvy chat processing.

## Why PostgreSQL?

PostgreSQL is suitable for HRMS data because employee records and leave transactions are structured, relational, and need reliable storage. The prototype uses SQLite locally for easy setup, but the backend is PostgreSQL-compatible through SQLAlchemy.

## Why document repository for policies?

HR policies are written documents with rules, conditions, eligibility statements, exceptions, and effective dates. These are better maintained in a document repository or HR knowledge base. In the prototype, `hr_policies.json` and `hr-policies.md` simulate this document repository.

## AskIvy data flow

```text
1. Employee asks a natural language HR question.
2. Frontend sends the question to the Flask backend.
3. Backend retrieves relevant HR policy content.
4. Backend checks employee profile and leave records from the database.
5. AskIvy reasoning service decides the most suitable HR route.
6. Backend returns a grounded answer to the React chatbot.
7. If the answer involves a leave request, the user can submit it.
8. Backend writes the pending leave request into the database.
```

## How this answers the AI questions

### Q1: How do we put the dynamic AI portion for HR policy?

The dynamic AI portion is placed in the backend between the HRMS database, policy repository, and chatbot response. This prevents the frontend from directly handling sensitive HR data or AI keys.

### Q2: How does the AI actually think?

It does not only fetch a policy. It interprets the situation, retrieves the policy, checks the employee profile, compares the policy rules with the user's case, and recommends the most suitable HR route.

### Q3: How do we translate “best stock to buy today” into HR policy?

The HR equivalent is: “What is the best HR option for my situation?” AskIvy recommends the safest HR route based on the employee's context, such as compassionate leave for bereavement, sick leave for illness, parental leave for childbirth or adoption, and annual leave for planned personal time.
