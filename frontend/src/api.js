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
  submitLeave: (employeeId, payload) => request(`/api/employees/${employeeId}/leave`, {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  askIvy: (employeeId, message) => request(ASKIVY_CHAT_PATH, {
    method: "POST",
    body: JSON.stringify({ employeeId, message }),
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
