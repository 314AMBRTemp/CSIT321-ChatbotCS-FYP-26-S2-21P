import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import ChatWidget from "./components/ChatWidget.jsx";

const BASE_PAGES = ["dashboard", "leave", "history", "profile", "policies"];

const PAGE_LABELS = {
  dashboard: "Dashboard",
  leave: "Leave",
  history: "My conversations",
  profile: "My profile",
  policies: "Policies",
  admin: "Support",
};

function formatDateRange(row) {
  return row.from === row.to ? row.from : `${row.from} → ${row.to}`;
}

// "In Progress" -> "in-progress", so it maps onto .s-in-progress in styles.css. A bare
// .toLowerCase() breaks on any multi-word status because the space lands in the class
// name literally -- caught once already when this table's own status pill did it.
function statusClass(status) {
  return `s-${status.toLowerCase().replace(/\s+/g, "-")}`;
}

// Mirrors HR_REQUEST_STATUSES in backend/app.py -- the backend still validates and rejects
// anything outside this list, so a mismatch here would just make the dropdown offer an
// option the server refuses, not a security issue.
const HR_REQUEST_STATUSES = ["Open", "In Progress", "Closed"];

function LeaveTable({ rows, onCancel }) {
  if (!rows?.length) return <p className="empty-text">No leave records yet.</p>;
  return (
    <div className="table-card">
      <table>
        <thead>
          <tr><th>Type</th><th>Dates</th><th>Days</th><th>Status</th><th>Via</th>{onCancel ? <th></th> : null}</tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.type}</td>
              <td>{formatDateRange(row)}</td>
              <td>{row.days}</td>
              <td><span className={`status-pill s-${row.status.toLowerCase()}`}>{row.status}</span></td>
              <td>{row.submittedVia || "Portal"}</td>
              {onCancel ? (
                <td>
                  {row.status === "Pending" ? (
                    <button className="btn-cancel-leave" onClick={() => onCancel(row.id)}>Cancel</button>
                  ) : null}
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LoginScreen({ users, onLogin }) {
  // Grouped by department rather than one flat list of 15. The roster is deliberately this
  // size -- the career-path matrix needs all five departments populated -- so the fix is
  // structure, not fewer people. Human Resources sorts first: it's the support account.
  const departments = useMemo(() => {
    const groups = new Map();
    for (const user of users) {
      if (!groups.has(user.department)) groups.set(user.department, []);
      groups.get(user.department).push(user);
    }
    return [...groups.entries()].sort(([a], [b]) => {
      if (a === "Human Resources") return -1;
      if (b === "Human Resources") return 1;
      return a.localeCompare(b);
    });
  }, [users]);

  return (
    <div className="login-screen">
      <div className="login-box">
        <div className="login-mark">iv</div>
        <h1>Lumen & Vale HRMS</h1>
        <p>Sign in to access the HR portal and AskIvy, your HR policy assistant.</p>
        {departments.map(([department, members]) => (
          <div className="login-dept" key={department}>
            <div className="login-dept-name">{department}</div>
            <div className="login-users">
              {members.map((user) => (
                <button className="login-user" key={user.id} onClick={() => onLogin(user)}>
                  <div className="lu-av">{user.initials}</div>
                  <div>
                    <div className="lu-name">
                      {user.name}
                      {user.isAdmin ? <span className="lu-badge">Support</span> : null}
                    </div>
                    <div className="lu-role">{user.role}{user.probation ? " · Probation" : ""}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DashboardPage({ data, onCancel }) {
  const employee = data.employee;
  const facts = data.facts;
  const recent = data.leaveHistory.slice(0, 3);

  return (
    <main className="page">
      <h1 className="page-title">Welcome back, {employee.name.split(" ")[0]}</h1>
      <p className="page-sub">Here's your HR snapshot for today.</p>
      <div className="stats">
        <div className="stat-card"><div className="stat-label">Annual leave remaining</div><div className="stat-value v-teal">{facts.annualLeaveRemaining} days</div></div>
        <div className="stat-card"><div className="stat-label">Sick leave remaining</div><div className="stat-value v-violet">{facts.sickLeaveRemaining} days</div></div>
        <div className="stat-card"><div className="stat-label">Pending requests</div><div className="stat-value v-amber">{data.pendingCount}</div></div>
      </div>
      <div className="section-title">Recent leave</div>
      <LeaveTable rows={recent} onCancel={onCancel} />
      <div className="info-banner">
        <div className="info-mark">iv</div>
        <div><strong>Need help?</strong> Click the AskIvy button in the bottom-right corner to ask HR policy questions, check eligibility, or submit a leave request through the chatbot.</div>
      </div>
    </main>
  );
}

function LeavePage({ data, employeeId, refresh, showToast, onCancel }) {
  const [form, setForm] = useState({ type: "Annual", from: "", to: "", reason: "" });

  async function submit(e) {
    e.preventDefault();
    if (!form.from || !form.to) {
      showToast("Please select dates.");
      return;
    }
    try {
      await api.submitLeave(employeeId, { ...form, submittedVia: "Portal" });
      showToast("Leave request submitted.");
      setForm({ type: "Annual", from: "", to: "", reason: "" });
      refresh();
    } catch (err) {
      showToast(err.message);
    }
  }

  return (
    <main className="page">
      <h1 className="page-title">Leave management</h1>
      <p className="page-sub">View your history and apply for new leave.</p>
      <div className="stats">
        <div className="stat-card"><div className="stat-label">Annual leave</div><div className="stat-value v-teal">{data.facts.annualLeaveRemaining} / {data.employee.annualLeaveEntitlement}</div></div>
        <div className="stat-card"><div className="stat-label">Sick leave</div><div className="stat-value v-violet">{data.facts.sickLeaveRemaining} / 14</div></div>
        <div className="stat-card"><div className="stat-label">Parental eligible</div><div className="stat-value v-teal">{data.facts.eligibleForParental ? "Yes" : "No"}</div></div>
      </div>

      <div className="section-title">Apply for leave</div>
      <form className="form-card" onSubmit={submit}>
        <div className="form-row">
          <div className="form-group">
            <label>Leave type</label>
            <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
              <option>Annual</option><option>Sick</option><option>Parental</option><option>Compassionate</option>
            </select>
          </div>
          <div className="form-group"><label>From</label><input type="date" value={form.from} onChange={(e) => setForm({ ...form, from: e.target.value })} /></div>
          <div className="form-group"><label>To</label><input type="date" value={form.to} onChange={(e) => setForm({ ...form, to: e.target.value })} /></div>
        </div>
        <div className="form-row">
          <div className="form-group"><label>Reason</label><textarea value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} placeholder="e.g. Family holiday" /></div>
        </div>
        <button className="btn-submit" type="submit">Submit request</button>
      </form>

      <div className="section-title">Leave history</div>
      <LeaveTable rows={data.leaveHistory} onCancel={onCancel} />
      <div className="hint-box">💡 You can also apply for leave by chatting with AskIvy — try: <em>“I need to take compassionate leave”</em></div>
    </main>
  );
}

function formatTimestamp(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

// Shared by the employee's own history and the support view. `showWho` adds the employee
// column, which only makes sense when the list spans more than one person.
function TranscriptList({ messages, showWho = false, emptyText }) {
  if (!messages?.length) return <p className="empty-text">{emptyText}</p>;
  return (
    <div className="transcript">
      {messages.map((m) => (
        <article className="transcript-item" key={m.id}>
          <div className="transcript-meta">
            {showWho ? <span className="transcript-who">{m.employeeName}</span> : null}
            <span className="transcript-time">{formatTimestamp(m.createdAt)}</span>
            {m.policyUsed ? <span className="transcript-source">§ {m.policyUsed}</span> : null}
            {m.unanswered ? <span className="transcript-flag">Unanswered</span> : null}
            {m.feedback ? <span className="transcript-feedback">{m.feedback === "up" ? "👍" : "👎"}</span> : null}
          </div>
          <div className="transcript-q">{m.question}</div>
          <div className="transcript-a">{m.response}</div>
        </article>
      ))}
    </div>
  );
}

function HistoryPage({ messages, hrRequests }) {
  return (
    <main className="page">
      <h1 className="page-title">My conversations</h1>
      <p className="page-sub">Everything you've asked AskIvy, newest first.</p>

      {/* 3.2.2 -- only shown once something's actually been raised, so this section
          doesn't clutter the page for the majority of employees who never have. */}
      {hrRequests?.length ? (
        <>
          <div className="section-title">My HR requests</div>
          <div className="table-card">
            <table>
              <thead>
                <tr><th>Raised</th><th>Topic</th><th>What I asked</th><th>Status</th></tr>
              </thead>
              <tbody>
                {hrRequests.map((row) => (
                  <tr key={row.id}>
                    <td>{new Date(row.createdAt).toLocaleString()}</td>
                    <td>{row.topic}</td>
                    <td>{row.question}</td>
                    <td><span className={`status-pill ${statusClass(row.status)}`}>{row.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      <div className="section-title">Transcript</div>
      <TranscriptList
        messages={messages}
        emptyText="You haven't asked AskIvy anything yet."
      />
    </main>
  );
}

function AnalyticsSection({ analytics }) {
  if (!analytics) return null;
  return (
    <>
      <div className="section-title">Usage analytics</div>
      <div className="stats">
        <div className="stat-card"><div className="stat-label">Unanswered</div><div className="stat-value v-amber">{analytics.unansweredCount} <span className="stat-sub">({Math.round(analytics.unansweredRate * 100)}%)</span></div></div>
        <div className="stat-card"><div className="stat-label">Feedback</div><div className="stat-value v-teal">👍 {analytics.feedback.up} · 👎 {analytics.feedback.down}</div></div>
        <div className="stat-card"><div className="stat-label">Open HR requests</div><div className="stat-value v-violet">{analytics.openHrRequests}</div></div>
      </div>

      <div className="two-col">
        <div>
          <div className="section-title">Most-asked topics</div>
          {analytics.topTopics.length ? (
            <div className="table-card">
              <table>
                <thead><tr><th>Topic</th><th>Questions</th></tr></thead>
                <tbody>
                  {analytics.topTopics.map((row) => (
                    <tr key={row.topic}><td>{row.topic}</td><td>{row.count}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="empty-text">No policy citations logged yet.</p>}
        </div>
        <div>
          <div className="section-title">HR requests by topic</div>
          {analytics.hrRequestsByTopic.length ? (
            <div className="table-card">
              <table>
                <thead><tr><th>Topic</th><th>Requests</th></tr></thead>
                <tbody>
                  {analytics.hrRequestsByTopic.map((row) => (
                    <tr key={row.topic}><td>{row.topic}</td><td>{row.count}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="empty-text">No HR requests raised yet.</p>}
        </div>
      </div>
    </>
  );
}

const emptyPolicyForm = { id: "", title: "", category: "", summary: "", rules: "" };

function PolicyManager({ policies, source, onCreate, onUpdate, onDelete }) {
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyPolicyForm);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);

  function startEdit(policy) {
    setEditingId(policy.id);
    setCreating(false);
    setForm({
      id: policy.id,
      title: policy.title,
      category: policy.category,
      summary: policy.summary,
      rules: (policy.rules || []).join("\n"),
    });
  }

  function startCreate() {
    setCreating(true);
    setEditingId(null);
    setForm(emptyPolicyForm);
  }

  function cancel() {
    setEditingId(null);
    setCreating(false);
    setForm(emptyPolicyForm);
  }

  async function save() {
    const payload = {
      title: form.title,
      category: form.category,
      summary: form.summary,
      // One rule per line in the textarea; blank lines dropped so a trailing newline
      // doesn't become an empty bullet in every policy answer.
      rules: form.rules.split("\n").map((r) => r.trim()).filter(Boolean),
    };
    setBusy(true);
    try {
      if (creating) {
        await onCreate({ id: form.id, ...payload });
      } else {
        await onUpdate(editingId, payload);
      }
      cancel();
    } catch {
      // Already surfaced via showToast in the App-level handler; the form stays open with
      // what was typed so a failed save doesn't also cost the user their edits.
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="section-title">
        Manage policies
        <span className="section-hint"> — also where FAQ-style entries go; there's no separate FAQ store, so a consistent answer never has two places to drift apart</span>
      </div>

      {source !== "database" ? (
        <div className="hint-box hint-warn">
          POLICY_SOURCE is currently "{source}", so the app is reading policies from the file,
          not the database. Edits here still save, but won't be visible until the source is
          switched back to "database".
        </div>
      ) : null}

      <div className="table-card">
        <table>
          <thead><tr><th>ID</th><th>Title</th><th>Category</th><th></th></tr></thead>
          <tbody>
            {policies.map((p) => (
              <tr key={p.id}>
                <td>{p.id}</td>
                <td>{p.title}</td>
                <td>{p.category}</td>
                <td className="table-actions">
                  <button className="btn-link" onClick={() => startEdit(p)}>Edit</button>
                  <button className="btn-link btn-link-danger" onClick={() => onDelete(p.id)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!creating && !editingId ? (
        <button className="cb-action-btn" onClick={startCreate}>Add policy</button>
      ) : (
        <div className="form-card">
          <div className="form-group">
            <label>ID (e.g. TRAVEL-01 — pick something new for an FAQ entry)</label>
            <input
              value={form.id}
              disabled={!creating}
              onChange={(e) => setForm({ ...form, id: e.target.value.toUpperCase() })}
            />
          </div>
          <div className="form-group">
            <label>Title</label>
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Category</label>
            <input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Summary</label>
            <textarea rows={2} value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Rules (one per line)</label>
            <textarea rows={5} value={form.rules} onChange={(e) => setForm({ ...form, rules: e.target.value })} />
          </div>
          <div className="table-actions">
            <button className="cb-action-btn" disabled={busy} onClick={save}>Save</button>
            <button className="btn-link" disabled={busy} onClick={cancel}>Cancel</button>
          </div>
        </div>
      )}
    </>
  );
}

function AdminPage({ data, users, filter, onFilterChange, hrRequests, onUpdateStatus, analytics, policies, policySource, onCreatePolicy, onUpdatePolicy, onDeletePolicy }) {
  const [unansweredOnly, setUnansweredOnly] = useState(false);
  const messages = unansweredOnly ? (data?.messages || []).filter((m) => m.unanswered) : data?.messages;

  return (
    <main className="page">
      <h1 className="page-title">Support — conversation log</h1>
      <p className="page-sub">
        Every AskIvy conversation across the organisation. Use this to spot questions the
        assistant handled badly or couldn't answer.
      </p>

      <div className="stats">
        <div className="stat-card"><div className="stat-label">Total messages</div><div className="stat-value v-violet">{data?.total ?? 0}</div></div>
        <div className="stat-card"><div className="stat-label">Showing</div><div className="stat-value v-teal">{data?.returned ?? 0}</div></div>
        <div className="stat-card"><div className="stat-label">Open HR requests</div><div className="stat-value v-amber">{hrRequests?.filter((r) => r.status === "Open").length ?? 0}</div></div>
      </div>

      <AnalyticsSection analytics={analytics} />

      {/* Sits above the transcript on purpose: these are the conversations where the
          employee actually asked for a human, so they are the ones needing action rather
          than review. */}
      <div className="section-title">Raised with HR</div>
      {hrRequests?.length ? (
        <div className="table-card">
          <table>
            <thead>
              <tr><th>Raised</th><th>Employee</th><th>Topic</th><th>What they asked</th><th>Manager copied</th><th>Assigned to</th><th>Status</th></tr>
            </thead>
            <tbody>
              {hrRequests.map((row) => (
                <tr key={row.id}>
                  <td>{new Date(row.createdAt).toLocaleString()}</td>
                  <td>{row.employeeName || row.employeeId}</td>
                  <td>{row.topic}</td>
                  <td>{row.question}</td>
                  <td>{row.managerEmail || "—"}</td>
                  <td>{row.assignedToName || "—"}</td>
                  <td>
                    <select
                      className={`status-select status-pill ${statusClass(row.status)}`}
                      value={row.status}
                      onChange={(e) => onUpdateStatus(row.id, e.target.value)}
                    >
                      {HR_REQUEST_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="hint-box">No one has asked AskIvy to raise anything with HR yet.</div>
      )}

      {policies ? (
        <PolicyManager
          policies={policies}
          source={policySource}
          onCreate={onCreatePolicy}
          onUpdate={onUpdatePolicy}
          onDelete={onDeletePolicy}
        />
      ) : null}

      <div className="form-card">
        <div className="form-group">
          <label>Filter by employee</label>
          <select value={filter} onChange={(e) => onFilterChange(e.target.value)}>
            <option value="">All employees</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>{u.name}</option>
            ))}
          </select>
        </div>
        <label className="checkbox-row">
          <input type="checkbox" checked={unansweredOnly} onChange={(e) => setUnansweredOnly(e.target.checked)} />
          Show only unanswered
        </label>
      </div>

      <div className="section-title">Transcript</div>
      <TranscriptList
        messages={messages}
        showWho
        emptyText={unansweredOnly ? "No unanswered questions in the current view." : "No conversations recorded yet."}
      />
    </main>
  );
}

function ProfilePage({ data }) {
  const employee = data.employee;
  const facts = data.facts;
  return (
    <main className="page">
      <h1 className="page-title">My profile</h1>
      <p className="page-sub">Your employment details as used by AskIvy.</p>
      <div className="profile-card">
        <div className="profile-avatar">{employee.initials}</div>
        <div className="profile-info">
          <div className="profile-name">{employee.name} <span className={`badge ${employee.probation ? "badge-amber" : "badge-green"}`}>{employee.probation ? "Probation" : "Confirmed"}</span></div>
          <div className="profile-role">{employee.role} · {employee.department}</div>
          <div className="profile-details">
            <InfoItem label="Start date" value={employee.startDate} />
            <InfoItem label="Tenure" value={employee.tenureYears < 1 ? "< 1 year" : `${employee.tenureYears} years`} />
            <InfoItem label="Salary band" value={employee.salaryBand} />
            <InfoItem label="Marital status" value={employee.maritalStatus} />
            <InfoItem label="Notice period" value={facts.notice} />
            <InfoItem label="Bonus eligible" value={facts.bonusEligible ? "Yes" : "No"} />
          </div>
        </div>
      </div>
      <div className="hint-box">AskIvy combines this structured HRMS profile data with the HR policy repository before giving personalised answers.</div>
    </main>
  );
}

function PoliciesPage({ policies }) {
  return (
    <main className="page">
      <h1 className="page-title">HR policy library</h1>
      <p className="page-sub">This represents the document repository / HR knowledge base used by AskIvy.</p>
      <div className="policy-grid">
        {policies.map((policy) => (
          <article className="policy-card" key={policy.id}>
            <div className="policy-id">{policy.id}</div>
            <h2>{policy.title}</h2>
            <p>{policy.summary}</p>
            <ul>
              {policy.rules.slice(0, 3).map((rule, index) => <li key={index}>{rule}</li>)}
            </ul>
          </article>
        ))}
      </div>
      <div className="hint-box">Prototype: policies are JSON/Markdown files. Real implementation: policies can come from SharePoint, Confluence, Supabase Storage, or an internal HR knowledge base.</div>
    </main>
  );
}

function InfoItem({ label, value }) {
  return <div className="pd-item"><div className="pd-label">{label}</div><div className="pd-value">{value}</div></div>;
}

function App() {
  const [users, setUsers] = useState([]);
  const [currentUser, setCurrentUser] = useState(null);
  const [activePage, setActivePage] = useState("dashboard");
  const [dashboardData, setDashboardData] = useState(null);
  const [leaveData, setLeaveData] = useState(null);
  const [profileData, setProfileData] = useState(null);
  const [policies, setPolicies] = useState([]);
  const [historyData, setHistoryData] = useState(null);
  const [myHrRequests, setMyHrRequests] = useState([]);
  const [adminData, setAdminData] = useState(null);
  const [adminFilter, setAdminFilter] = useState("");
  const [hrRequests, setHrRequests] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  // Distinct from `policies` above (the public read-only list on the Policies page) --
  // this one is fetched fresh per admin action so an edit is reflected immediately without
  // waiting for the next scheduled refresh.
  const [adminPolicies, setAdminPolicies] = useState(null);
  const [policySource, setPolicySource] = useState("database");
  const [toast, setToast] = useState("");
  const [loading, setLoading] = useState(false);

  const employeeId = currentUser?.id;
  // The Support tab only exists for admins. Server-side the route 403s on its own, so a
  // hidden tab is convenience, not the access control.
  const pages = currentUser?.isAdmin ? [...BASE_PAGES, "admin"] : BASE_PAGES;

  const activeData = useMemo(() => {
    if (activePage === "dashboard") return dashboardData;
    if (activePage === "leave") return leaveData;
    if (activePage === "profile") return profileData;
    return null;
  }, [activePage, dashboardData, leaveData, profileData]);

  useEffect(() => {
    api.users().then(setUsers).catch(() => setUsers([]));
    api.policies().then(setPolicies).catch(() => setPolicies([]));
  }, []);

  useEffect(() => {
    if (!employeeId) return;
    refreshAll();
  }, [employeeId]);

  // Loaded separately from refreshAll: it's admin-only, and it re-fetches when the filter
  // changes rather than when the employee's own data does.
  useEffect(() => {
    if (!currentUser?.isAdmin || activePage !== "admin") return;
    api.adminChats(currentUser.id, { employeeId: adminFilter })
      .then(setAdminData)
      .catch((err) => showToast(err.message));
    refreshHrRequests();
    api.adminAnalytics(currentUser.id)
      .then(setAnalytics)
      .catch(() => setAnalytics(null));
    refreshAdminPolicies();
  }, [currentUser?.id, currentUser?.isAdmin, activePage, adminFilter]);

  function refreshAdminPolicies() {
    if (!currentUser?.isAdmin) return;
    api.adminPolicies(currentUser.id)
      .then((res) => { setAdminPolicies(res.policies); setPolicySource(res.source); })
      .catch(() => setAdminPolicies([]));
  }

  // Not filtered by employee: there are far fewer of these than chat messages, and a
  // support user opening this tab wants to see everything outstanding. Also called
  // directly after a status update (3.2.5) so the table reflects it immediately rather
  // than waiting for the next filter change to re-trigger the effect above.
  function refreshHrRequests() {
    if (!currentUser?.isAdmin) return;
    api.adminHrRequests(currentUser.id)
      .then(setHrRequests)
      .catch(() => setHrRequests([]));
  }

  async function updateHrRequestStatus(requestId, status) {
    try {
      await api.adminUpdateHrRequestStatus(currentUser.id, requestId, status);
      refreshHrRequests();
    } catch (err) {
      showToast(err.message || "Couldn't update that request's status.");
    }
  }

  async function createPolicy(policy) {
    try {
      await api.adminCreatePolicy(currentUser.id, policy);
      showToast(`Policy "${policy.id}" created.`);
      refreshAdminPolicies();
    } catch (err) {
      showToast(err.message || "Couldn't create that policy.");
      throw err; // keeps the PolicyManager form open on failure
    }
  }

  async function updatePolicy(policyId, policy) {
    try {
      await api.adminUpdatePolicy(currentUser.id, policyId, policy);
      showToast(`Policy "${policyId}" updated.`);
      refreshAdminPolicies();
    } catch (err) {
      showToast(err.message || "Couldn't save that policy.");
      throw err;
    }
  }

  async function deletePolicy(policyId) {
    try {
      await api.adminDeletePolicy(currentUser.id, policyId);
      showToast(`Policy "${policyId}" deleted.`);
      refreshAdminPolicies();
    } catch (err) {
      showToast(err.message || "Couldn't delete that policy.");
    }
  }

  function showToast(message) {
    setToast(message);
    setTimeout(() => setToast(""), 3000);
  }

  async function refreshAll() {
    if (!employeeId) return;
    setLoading(true);
    try {
      const [dashboard, leave, profile, history, hrRequests] = await Promise.all([
        api.dashboard(employeeId),
        api.leave(employeeId),
        api.profile(employeeId),
        api.chatHistory(employeeId),
        api.employeeHrRequests(employeeId),
      ]);
      setDashboardData(dashboard);
      setLeaveData(leave);
      setProfileData(profile);
      setHistoryData(history);
      setMyHrRequests(hrRequests);
    } catch (err) {
      showToast(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function cancelLeave(leaveId) {
    if (!window.confirm("Cancel this pending leave request?")) return;
    try {
      await api.cancelLeave(employeeId, leaveId);
      showToast("Leave request cancelled.");
      refreshAll();
    } catch (err) {
      showToast(err.message);
    }
  }

  function logout() {
    setCurrentUser(null);
    setActivePage("dashboard");
    setDashboardData(null);
    setLeaveData(null);
    setProfileData(null);
  }

  if (!currentUser) {
    return <LoginScreen users={users} onLogin={setCurrentUser} />;
  }

  return (
    <>
      <nav className="topnav">
        <div className="topnav-left">
          <div className="topnav-brand"><div className="topnav-mark">iv</div> Lumen & Vale</div>
          <div className="topnav-links">
            {pages.map((page) => (
              <button key={page} className={activePage === page ? "active" : ""} onClick={() => setActivePage(page)}>
                {PAGE_LABELS[page]}
              </button>
            ))}
          </div>
        </div>
        <div className="topnav-right">
          <span className="topnav-name">{currentUser.name}</span>
          <div className="topnav-avatar">{currentUser.initials}</div>
          <button className="topnav-logout" onClick={logout}>Sign out</button>
        </div>
      </nav>

      {loading && !activeData ? <main className="page"><p>Loading HRMS data...</p></main> : null}
      {activePage === "dashboard" && dashboardData ? <DashboardPage data={dashboardData} onCancel={cancelLeave} /> : null}
      {activePage === "leave" && leaveData ? <LeavePage data={leaveData} employeeId={employeeId} refresh={refreshAll} showToast={showToast} onCancel={cancelLeave} /> : null}
      {activePage === "history" && historyData ? <HistoryPage messages={historyData.messages} hrRequests={myHrRequests} /> : null}
      {activePage === "profile" && profileData ? <ProfilePage data={profileData} /> : null}
      {activePage === "policies" ? <PoliciesPage policies={policies} /> : null}
      {activePage === "admin" && currentUser.isAdmin ? (
        <AdminPage
          data={adminData}
          users={users}
          filter={adminFilter}
          onFilterChange={setAdminFilter}
          hrRequests={hrRequests}
          onUpdateStatus={updateHrRequestStatus}
          analytics={analytics}
          policies={adminPolicies}
          policySource={policySource}
          onCreatePolicy={createPolicy}
          onUpdatePolicy={updatePolicy}
          onDeletePolicy={deletePolicy}
        />
      ) : null}

      <ChatWidget employee={currentUser} onLeaveSubmitted={refreshAll} showToast={showToast} />
      {toast ? <div className="toast show">{toast}</div> : null}
    </>
  );
}

export default App;
