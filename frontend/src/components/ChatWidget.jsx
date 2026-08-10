import { useEffect, useRef, useState } from "react";
import { api } from "../api";

const suggestions = [
  "My cousin passed away, is there leave for this?",
  "How many leave days do I have?",
  "Am I eligible for parental leave?",
  "Cancel my pending leave request",
  "What would it take to move into Sales?",
];

function ChatWidget({ employee, onLeaveSubmitted, showToast }) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const bodyRef = useRef(null);
  const inputRef = useRef(null);

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
        { role: "assistant", ...answer },
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
              onButton={ask}
              isLast={index === messages.length - 1}
              loading={loading}
            />
          ))}
        </div>

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

function Message({ message, employee, onSubmitLeave, onButton, isLast, loading }) {
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
