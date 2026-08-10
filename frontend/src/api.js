const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:5000";

// Which chatbot engine the widget talks to. Both return the identical JSON
// shape, so switching engines needs no component changes.
//   "rules" (default) -> /api/askivy/chat       original rule-based engine
//   "rasa"            -> /api/askivy/chat-rasa  Rasa CALM + Claude
// Set VITE_ASKIVY_ENGINE=rasa in frontend/.env.local to switch.
const ASKIVY_ENGINE = import.meta.env.VITE_ASKIVY_ENGINE || "rules";
const ASKIVY_CHAT_PATH =
  ASKIVY_ENGINE === "rasa" ? "/api/askivy/chat-rasa" : "/api/askivy/chat";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

export const api = {
  health: () => request("/api/health"),
  users: () => request("/api/users"),
  dashboard: (employeeId) => request(`/api/employees/${employeeId}/dashboard`),
  leave: (employeeId) => request(`/api/employees/${employeeId}/leave`),
  profile: (employeeId) => request(`/api/employees/${employeeId}`),
  policies: () => request("/api/policies"),
  chatHistory: (employeeId) => request(`/api/employees/${employeeId}/chat`),
  // Records something the employee asked AskIvy to take to HR. Fired by the "Yes, raise it"
  // button, which only appears when the reply actually offered.
  raiseHrRequest: (payload) => request("/api/hr-requests", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  adminHrRequests: (requesterId) => request(`/api/admin/hr-requests?requesterId=${encodeURIComponent(requesterId)}`),
  // "up" / "down" / null (null clears a previous rating).
  rateMessage: (chatMessageId, feedback) => request(`/api/chat-messages/${chatMessageId}/feedback`, {
    method: "POST",
    body: JSON.stringify({ feedback }),
  }),
  adminAnalytics: (requesterId) => request(`/api/admin/analytics?requesterId=${encodeURIComponent(requesterId)}`),
  adminPolicies: (requesterId) => request(`/api/admin/policies?requesterId=${encodeURIComponent(requesterId)}`),
  adminCreatePolicy: (requesterId, policy) => request(`/api/admin/policies?requesterId=${encodeURIComponent(requesterId)}`, {
    method: "POST",
    body: JSON.stringify(policy),
  }),
  adminUpdatePolicy: (requesterId, policyId, policy) => request(`/api/admin/policies/${encodeURIComponent(policyId)}?requesterId=${encodeURIComponent(requesterId)}`, {
    method: "PUT",
    body: JSON.stringify(policy),
  }),
  adminDeletePolicy: (requesterId, policyId) => request(`/api/admin/policies/${encodeURIComponent(policyId)}?requesterId=${encodeURIComponent(requesterId)}`, {
    method: "DELETE",
  }),
  adminChats: (requesterId, { employeeId = "", limit = 200 } = {}) => {
    const params = new URLSearchParams({ requesterId, limit: String(limit) });
    if (employeeId) params.set("employeeId", employeeId);
    return request(`/api/admin/chats?${params.toString()}`);
  },
  submitLeave: (employeeId, payload) => request(`/api/employees/${employeeId}/leave`, {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  cancelLeave: (employeeId, leaveId) => request(`/api/employees/${employeeId}/leave/${leaveId}/cancel`, {
    method: "POST",
  }),
  // `displayText` is what the user actually saw themselves send. For a clicked button that
  // is the button's title, while `message` carries the /SetSlots(...) payload the bot needs.
  // Without it the conversation log records the payload, which is unreadable in the support
  // view.
  askIvy: (employeeId, message, displayText) => request(ASKIVY_CHAT_PATH, {
    method: "POST",
    body: JSON.stringify({ employeeId, message, displayText }),
  }),
  askIvyEngine: () => ASKIVY_ENGINE,
  askIvyRasaHealth: () => request("/api/askivy/rasa/health"),
  askIvyRasaReset: (employeeId) => request("/api/askivy/rasa/reset", {
    method: "POST",
    body: JSON.stringify({ employeeId }),
  }),
  askIvySubmitLeave: (employeeId, payload) => request("/api/askivy/submit-leave", {
    method: "POST",
    body: JSON.stringify({ employeeId, ...payload }),
  }),
};
