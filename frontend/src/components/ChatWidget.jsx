import { useEffect, useRef, useState } from "react";
import { api } from "../api";

// Suggestion chips are unprompted -- the app puts these words in the employee's mouth
// before they've said anything. So no bereavement phrasing here: the bot still handles
// "my cousin passed away" perfectly well when someone genuinely types it, but offering it
// as a sample prompt reads as tone-deaf.
const suggestions = [
  "I need to take compassionate leave",
  "How many leave days do I have?",
  "Am I eligible for parental leave?",
  "Cancel my pending leave request",
  "What would it take to move into Sales?",
];

// Session timeout warning (3.1.4). There's no real server-side session to expire --
// sender_id is the employee id and the Rasa tracker persists indefinitely -- so this is a
// purely frontend idle clock over an open widget, checked on a slow interval rather than
// nested setTimeouts. Warn once, then actually reset (clear the transcript + the Rasa
// tracker) rather than leaving the warning to rot forever if nobody comes back.
const IDLE_WARNING_MS = 4 * 60 * 1000;
const IDLE_RESET_MS = 5 * 60 * 1000;
const IDLE_CHECK_INTERVAL_MS = 10 * 1000;

function ChatWidget({ employee, onLeaveSubmitted, showToast }) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showTimeoutWarning, setShowTimeoutWarning] = useState(false);
  const bodyRef = useRef(null);
  const inputRef = useRef(null);
  const lastActivityRef = useRef(Date.now());

  function bumpActivity() {
    lastActivityRef.current = Date.now();
    setShowTimeoutWarning(false);
  }

  // Idle clock: only runs while the widget is open, so a closed tab doesn't silently reset
  // conversation state nobody's looking at. Polls rather than a single setTimeout so the
  // warning threshold and the reset threshold don't need two coordinated timers re-armed
  // on every message.
  useEffect(() => {
    if (!open) return undefined;
    bumpActivity(); // opening the widget itself counts as activity
    const interval = setInterval(() => {
      const idleFor = Date.now() - lastActivityRef.current;
      if (idleFor >= IDLE_RESET_MS) {
        setMessages([]);
        if (employee?.id) api.askIvyRasaReset(employee.id).catch(() => {});
        showToast("Conversation reset after 5 minutes of inactivity.");
        bumpActivity();
      } else if (idleFor >= IDLE_WARNING_MS) {
        setShowTimeoutWarning(true);
      }
    }, IDLE_CHECK_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [open, employee?.id]);

  useEffect(() => {
    setMessages([]);
    setInput("");
    // Clear the Rasa tracker too, not just the transcript. sender_id is the employee id,
    // so an abandoned half-finished flow otherwise survives a sign-out: the widget looks
    // empty but the bot's next reply picks up mid-flow ("How many days do you need?").
    // Best-effort -- a failure here shouldn't stop the widget rendering.
    if (employee?.id) api.askIvyRasaReset(employee.id).catch(() => {});
  }, [employee?.id]);

  useEffect(() => {
    if (!bodyRef.current) return;
    bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [messages, open]);

  useEffect(() => {
    if (!inputRef.current) return;
    inputRef.current.style.height = "auto";
    inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 130)}px`;
  }, [input]);

  // `displayText` lets a button send its /SetSlots(...) payload while the
  // transcript shows the human-readable title the user actually clicked.
  async function ask(customQuestion, displayText) {
    const question = (customQuestion || input).trim();
    if (!question || loading) return;

    bumpActivity();
    setInput("");
    setLoading(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", text: displayText || question },
      { role: "thinking", steps: [
        { tag: "Understand", text: "Reading your HR situation" },
        { tag: "Retrieve", text: "Searching relevant policy documents" },
        { tag: "Context", text: "Checking HRMS profile and leave data" },
        { tag: "Decide", text: "Preparing recommendation" },
      ]},
    ]);

    try {
      const answer = await api.askIvy(employee.id, question, displayText);
      setMessages((prev) => [
        ...prev.filter((m) => m.role !== "thinking"),
        // `question` rides along so that if this reply offers to raise something with HR,
        // the request records what was actually asked rather than the bot's own wording.
        { role: "assistant", question, ...answer },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev.filter((m) => m.role !== "thinking"),
        { role: "assistant", text: err.message || "AskIvy is currently unavailable.", source: null },
      ]);
    } finally {
      setLoading(false);
    }
  }

  // Accepting the bot's offer to take something to HR. The row it writes is what the
  // Support tab shows, so an offer the employee accepted always leaves a trace someone can
  // act on -- an offer that led nowhere would be worse than not offering at all.
  async function raiseHrRequest(message, index) {
    try {
      await api.raiseHrRequest({
        employeeId: employee.id,
        topic: message.policyTopic,
        policyId: message.policyId,
        question: message.question,
        situation: message.situation,
      });
      // Mark this specific reply as actioned so the card can't be clicked twice.
      setMessages((prev) => prev.map((m, i) => (i === index ? { ...m, hrRequestRaised: true } : m)));
      showToast(
        employee.managerName
          ? `Raised with HR, copying ${employee.managerName}.`
          : "Raised with HR.",
      );
    } catch (err) {
      showToast(err.message || "Couldn't raise that with HR.");
    }
  }

  // Thumbs up/down (3.5.1). Clicking the already-selected thumb clears the rating (sends
  // null) rather than doing nothing -- a misclick shouldn't be permanent. Only messages
  // that actually made it into chat_messages carry a chatMessageId; the local
  // API-unavailable error bubble doesn't, so it correctly gets no thumbs at all.
  async function rateFeedback(index, message, value) {
    const next = message.feedback === value ? null : value;
    setMessages((prev) => prev.map((m, i) => (i === index ? { ...m, feedback: next } : m)));
    try {
      await api.rateMessage(message.chatMessageId, next);
    } catch (err) {
      // Roll back on failure rather than leave the UI claiming a rating that didn't save.
      setMessages((prev) => prev.map((m, i) => (i === index ? { ...m, feedback: message.feedback } : m)));
      showToast(err.message || "Couldn't save that rating.");
    }
  }

  async function submitLeave(suggestedLeave) {
    if (!suggestedLeave) return;
    try {
      const result = await api.askIvySubmitLeave(employee.id, suggestedLeave);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `${result.message} It is now pending manager approval. You can check it on the Leave page.`,
          source: null,
          canSubmitLeave: false,
        },
      ]);
      showToast("Leave request submitted via AskIvy.");
      onLeaveSubmitted();
    } catch (err) {
      showToast(err.message);
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      ask();
    }
  }

  return (
    <>
      <button className="chat-fab" onClick={() => setOpen(true)}>iv</button>
      <section className={`chat-window ${open ? "open" : ""}`}>
        <div className="chat-header">
          <div className="chat-header-left">
            <div className="chat-header-mark">iv</div>
            <div><div className="chat-header-name">AskIvy</div><div className="chat-header-sub">HR policy assistant</div></div>
          </div>
          <button className="chat-close" onClick={() => setOpen(false)}>✕</button>
        </div>

        <div className="chat-body" ref={bodyRef}>
          {messages.length === 0 ? (
            <div className="chat-empty">
              <div className="chat-empty-title">Hi {employee.name.split(" ")[0]}!</div>
              <div className="chat-empty-body">I can recommend the best HR route, check your eligibility, or help submit a leave request.</div>
              <div className="chat-chips">
                {suggestions.map((s) => <button className="chat-chip" key={s} onClick={() => ask(s)}>{s}</button>)}
              </div>
            </div>
          ) : messages.map((message, index) => (
            <Message
              key={index}
              message={message}
              employee={employee}
              onSubmitLeave={submitLeave}
              onRaiseHr={() => raiseHrRequest(message, index)}
              onRateFeedback={(value) => rateFeedback(index, message, value)}
              onButton={ask}
              isLast={index === messages.length - 1}
              loading={loading}
            />
          ))}
        </div>

        {showTimeoutWarning ? (
          <div className="chat-idle-warning">
            Still there? This conversation will reset after a minute of inactivity.
            <button className="chat-idle-dismiss" onClick={bumpActivity}>I'm still here</button>
          </div>
        ) : null}

        <div className="chat-input-bar">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask about a policy or apply for leave..."
            rows={1}
          />
          <button className="chat-send" disabled={loading} onClick={() => ask()}>Ask</button>
        </div>
      </section>
    </>
  );
}

function Message({ message, employee, onSubmitLeave, onRaiseHr, onRateFeedback, onButton, isLast, loading }) {
  if (message.role === "user") {
    return <div className="cb-user"><div className="cb-user-bubble">{message.text}</div></div>;
  }

  if (message.role === "thinking") {
    return (
      <div className="cb-think">
        <div className="cb-think-head"><span className="cb-think-pulse" />AskIvy is reasoning</div>
        {message.steps.map((step, index) => <div className="cb-think-step" key={index}><span className="cb-think-tag">{step.tag}</span>{step.text}</div>)}
      </div>
    );
  }

  return (
    <div className="cb-bot">
      <div className="cb-bot-mark">iv</div>
      <div className="cb-bot-bubble">
        {message.isRecommendation ? <div className="cb-bot-tag action">Recommendation</div> : <div className="cb-bot-tag personal">Personalised for {employee.name.split(" ")[0]}</div>}
        <div className="cb-bot-text">{message.text}</div>
        {message.source ? <div className="cb-source">§ {message.source}</div> : null}
        {/* Available on every past reply, not just the newest -- rating something you asked
            two turns ago is still meaningful. Only shown once the reply is actually a
            logged row (chatMessageId present); the local network-error bubble isn't. */}
        {message.chatMessageId ? (
          <div className="cb-feedback">
            <button
              className={`cb-feedback-btn ${message.feedback === "up" ? "active" : ""}`}
              aria-label="Helpful"
              onClick={() => onRateFeedback("up")}
            >
              👍
            </button>
            <button
              className={`cb-feedback-btn ${message.feedback === "down" ? "active" : ""}`}
              aria-label="Not helpful"
              onClick={() => onRateFeedback("down")}
            >
              👎
            </button>
          </div>
        ) : null}
        {/* Only the newest reply keeps its buttons — stale choices from earlier
            turns are no longer answerable. The rule-based engine sends none. */}
        {isLast && message.buttons?.length ? (
          <div className="cb-buttons">
            {message.buttons.map((button) => (
              <button
                className="cb-btn"
                key={button.payload}
                disabled={loading}
                onClick={() => onButton(button.payload, button.title)}
              >
                {button.title}
              </button>
            ))}
          </div>
        ) : null}
        {/* The reply ended by offering to take this to HR, so give them a way to say yes.
            Only on the newest reply, like the other buttons -- and it disappears once
            actioned rather than silently writing a second row. */}
        {isLast && message.canRaiseHrRequest ? (
          message.hrRequestRaised ? (
            <div className="cb-action-card">
              <strong>Raised with HR</strong><br />
              {employee.managerEmail
                ? `${employee.managerName} has been copied.`
                : "HR will follow up with you."}
            </div>
          ) : (
            <div className="cb-action-card">
              <strong>Raise this with HR</strong><br />
              {message.policyTopic}
              {employee.managerName ? ` · copying ${employee.managerName}` : ""}<br />
              <button className="cb-action-btn" disabled={loading} onClick={onRaiseHr}>Yes, raise it</button>
            </div>
          )
        ) : null}
        {message.canSubmitLeave && message.suggestedLeave ? (
          <div className="cb-action-card">
            <strong>Leave request ready</strong><br />
            {message.suggestedLeave.type} leave · {message.suggestedLeave.days} day{message.suggestedLeave.days > 1 ? "s" : ""}<br />
            <button className="cb-action-btn" onClick={() => onSubmitLeave(message.suggestedLeave)}>Submit this request</button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default ChatWidget;
