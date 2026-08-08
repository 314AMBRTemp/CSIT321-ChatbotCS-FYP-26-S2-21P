import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import ChatWidget from "./components/ChatWidget.jsx";

const pages = ["dashboard", "leave", "profile", "policies"];

function formatDateRange(row) {
  return row.from === row.to ? row.from : `${row.from} → ${row.to}`;
}

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
  return (
    <div className="login-screen">
      <div className="login-box">
        <div className="login-mark">iv</div>
        <h1>Lumen & Vale HRMS</h1>
        <p>Sign in to access the HR portal and AskIvy, your HR policy assistant.</p>
        <div className="login-users">
          {users.map((user) => (
            <button className="login-user" key={user.id} onClick={() => onLogin(user)}>
              <div className="lu-av">{user.initials}</div>
              <div>
                <div className="lu-name">{user.name}</div>
                <div className="lu-role">{user.role} · {user.department}{user.probation ? " · Probation" : ""}</div>
              </div>
            </button>
          ))}
        </div>
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
      <div className="hint-box">💡 You can also apply for leave by chatting with AskIvy — try: <em>“My cousin passed away, is there leave for this?”</em></div>
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
  const [toast, setToast] = useState("");
  const [loading, setLoading] = useState(false);

  const employeeId = currentUser?.id;

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

  function showToast(message) {
    setToast(message);
    setTimeout(() => setToast(""), 3000);
  }

  async function refreshAll() {
    if (!employeeId) return;
    setLoading(true);
    try {
      const [dashboard, leave, profile] = await Promise.all([
        api.dashboard(employeeId),
        api.leave(employeeId),
        api.profile(employeeId),
      ]);
      setDashboardData(dashboard);
      setLeaveData(leave);
      setProfileData(profile);
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
                {page === "dashboard" ? "Dashboard" : page === "leave" ? "Leave" : page === "profile" ? "My profile" : "Policies"}
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
      {activePage === "profile" && profileData ? <ProfilePage data={profileData} /> : null}
      {activePage === "policies" ? <PoliciesPage policies={policies} /> : null}

      <ChatWidget employee={currentUser} onLeaveSubmitted={refreshAll} showToast={showToast} />
      {toast ? <div className="toast show">{toast}</div> : null}
    </>
  );
}

export default App;
