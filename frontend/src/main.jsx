import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const EXAMPLE =
  "Users should be able to log in using their email and password. If the password is incorrect five times, the account should be temporarily locked.";

const CATEGORY_COLORS = {
  positive: "#57d69a",
  negative: "#65a9ff",
  boundary: "#aa8bff",
  security: "#ffbd69",
  edge: "#ff7b9b",
};

const STAGES = ["ingested", "analyzed", "planned", "generated", "executed"];

async function postJson(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "same-origin",
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `Request failed (${response.status})`);
  }
  return data;
}

async function getJson(path) {
  const response = await fetch(path, { credentials: "same-origin" });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `Request failed (${response.status})`);
  }
  return data;
}

function downloadFile(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

function PieChart({ cases }) {
  const counts = cases.reduce((result, testCase) => {
    result[testCase.category] = (result[testCase.category] || 0) + 1;
    return result;
  }, {});
  const entries = Object.entries(counts);
  const total = cases.length;
  let angle = -Math.PI / 2;

  const slices = entries.map(([category, count]) => {
    const start = angle;
    angle += (count / total) * Math.PI * 2;
    const end = angle;
    if (count === total) {
      return (
        <circle
          key={category}
          cx="110"
          cy="110"
          r="98"
          fill={CATEGORY_COLORS[category] || "#8ca0b8"}
          stroke="#111827"
          strokeWidth="2"
        />
      );
    }
    const startX = 110 + 98 * Math.cos(start);
    const startY = 110 + 98 * Math.sin(start);
    const endX = 110 + 98 * Math.cos(end);
    const endY = 110 + 98 * Math.sin(end);
    const largeArc = end - start > Math.PI ? 1 : 0;
    const path = [
      "M 110 110",
      `L ${startX} ${startY}`,
      `A 98 98 0 ${largeArc} 1 ${endX} ${endY}`,
      "Z",
    ].join(" ");
    return (
      <path
        key={category}
        d={path}
        fill={CATEGORY_COLORS[category] || "#8ca0b8"}
        stroke="#111827"
        strokeWidth="2"
      />
    );
  });

  return (
    <section className="panel content-panel chart-panel" aria-labelledby="chartTitle">
      <div className="section-head">
        <div>
          <h2 id="chartTitle">Scenario mix</h2>
          <p>Generated scenarios grouped by category.</p>
        </div>
        <span className="chart-total">{total} total</span>
      </div>
      {total ? (
        <div className="chart-content">
          <svg
            className="pie-chart"
            viewBox="0 0 220 220"
            role="img"
            aria-label={`Pie chart of ${total} scenarios by category`}
          >
            <title>
              {entries
                .map(([category, count]) => `${category}: ${count}`)
                .join(", ")}
            </title>
            {slices}
          </svg>
          <ul className="chart-legend">
            {entries.map(([category, count]) => (
              <li key={category}>
                <span
                  className="legend-dot"
                  style={{ backgroundColor: CATEGORY_COLORS[category] || "#8ca0b8" }}
                />
                <span className="legend-name">{category}</span>
                <strong>{count}</strong>
                <small>{Math.round((count / total) * 100)}%</small>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="empty-chart">No scenarios were identified for this requirement.</p>
      )}
    </section>
  );
}

function AnalysisMap({ plan }) {
  const { analysis, cases, missing_requirements: missing } = plan;
  const categoryCounts = cases.reduce((counts, testCase) => {
    counts[testCase.category] = (counts[testCase.category] || 0) + 1;
    return counts;
  }, {});
  const readyCount = cases.filter((testCase) => testCase.executable).length;
  const clarificationCount = cases.length - readyCount;
  const parameters = analysis.parameters || {};

  return (
    <section className="panel flow-panel" aria-labelledby="flowTitle">
      <div className="section-head">
        <div>
          <h2 id="flowTitle">Analysis map</h2>
          <p>A visual summary of how this requirement becomes reviewed test scenarios.</p>
        </div>
        <span className="chip">{cases.length} scenarios mapped</span>
      </div>
      <div className="flow-and-chart">
        <div className="flow-left">
          <div className="flow-diagram" role="img" aria-label="Requirement, analysis, and test scenario pipeline">
            <div className="flow-node source">
              <div className="flow-kicker"><span className="flow-index">1</span> Requirement</div>
              <p>{plan.requirement.text}</p>
            </div>
            <div className="flow-arrow" aria-hidden="true">→</div>
            <div className="flow-node analyzer">
              <div className="flow-kicker"><span className="flow-index">2</span> Analyzer</div>
              <p>Extracted rules and requirement details</p>
              <div className="flow-stats">
                <span className="flow-stat">{analysis.rules.length} rules</span>
                {analysis.actors.map((actor) => (
                  <span className="flow-stat" key={actor}>Actor: {actor}</span>
                ))}
                {parameters.max_failed_attempts && (
                  <span className="flow-stat">Lock threshold: {parameters.max_failed_attempts}</span>
                )}
              </div>
            </div>
            <div className="flow-arrow" aria-hidden="true">→</div>
            <div className="flow-node planner">
              <div className="flow-kicker"><span className="flow-index">3</span> Scenario planner</div>
              <p>{cases.length} scenarios across {Object.keys(categoryCounts).length} categories</p>
              <div className="flow-categories">
                {Object.entries(categoryCounts).map(([category, count]) => (
                  <span className="flow-category" key={category}>{category} · {count}</span>
                ))}
              </div>
            </div>
          </div>
          <div className="flow-outcomes">
            <div className="flow-outcome">
              <span className="flow-outcome-count">{readyCount}</span>
              <span>
                <strong>Ready for your approval</strong>
                <small>Supported scenarios can be generated as tests; execution is a separate choice.</small>
              </span>
            </div>
            <div className="flow-outcome needs-info">
              <span className="flow-outcome-count">{clarificationCount}</span>
              <span>
                <strong>Need a template or clarification</strong>
                <small>
                  {clarificationCount} scenario{clarificationCount === 1 ? "" : "s"} cannot run as-is ·{" "}
                  {missing.length} clarification question{missing.length === 1 ? "" : "s"} identified.
                </small>
              </span>
            </div>
          </div>
        </div>
        <PieChart cases={cases} />
      </div>
    </section>
  );
}

function ScenarioReview({ plan, selected, setSelected, toggleAll }) {
  return (
    <div className="panel content-panel scenario-panel">
      <div className="section-head">
        <div>
          <h2>02 / Review generated scenarios</h2>
          <p>Select the cases you approve for test generation.</p>
        </div>
        <button className="subtle-button" onClick={toggleAll}>
          {selected.size ? "Deselect all" : "Select all"}
        </button>
      </div>
      <div className="case-list">
        {plan.cases.map((testCase) => (
          <label
            className={`case ${testCase.executable ? "" : "unavailable"}`}
            key={testCase.id}
          >
            <input
              type="checkbox"
              checked={selected.has(testCase.id)}
              disabled={!testCase.executable}
              onChange={() => setSelected((current) => {
                const next = new Set(current);
                if (next.has(testCase.id)) next.delete(testCase.id);
                else next.add(testCase.id);
                return next;
              })}
              aria-label={`Approve ${testCase.title}`}
            />
            <span>
              <strong>{testCase.title}</strong>
              <small>
                {testCase.id} · traces {testCase.rule_ids.join(", ")}
                {testCase.reason ? ` · ${testCase.reason}` : ""}
              </small>
            </span>
            <span className="category">{testCase.category}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

function AnalysisDetails({ plan }) {
  const parameters = plan.analysis.parameters || {};
  const chips = [
    ...plan.analysis.actors.map((actor) => `Actor: ${actor}`),
    ...(parameters.feature ? [`Feature: ${parameters.feature}`] : []),
    ...(parameters.max_failed_attempts ? [`Threshold: ${parameters.max_failed_attempts} attempts`] : []),
    `Rules: ${plan.analysis.rules.length}`,
    `Scenarios: ${plan.cases.length}`,
  ];

  return (
    <div className="analysis-side">
      <div className="panel content-panel">
        <h2>Requirement analysis</h2>
        <div className="chips">
          {chips.map((chip) => <span className="chip" key={chip}>{chip}</span>)}
        </div>
        <div className="rule-list">
          {plan.analysis.rules.map((rule) => (
            <div className="rule" key={rule.id}>
              <strong>{rule.id}</strong> &nbsp; {rule.text}
            </div>
          ))}
        </div>
      </div>
      <div className="panel content-panel clarifications">
        <h2>Clarifications needed</h2>
        <p className="muted">Ambiguities are surfaced rather than silently assumed.</p>
        <ul className="missing">
          {plan.missing_requirements.length ? plan.missing_requirements.map((question) => (
            <li key={question}>{question}</li>
          )) : <li>No clarification questions detected.</li>}
        </ul>
      </div>
    </div>
  );
}

function ResultDashboard({ result }) {
  const [tab, setTab] = useState("cases");
  const { report } = result;
  const summary = report.summary;
  const metrics = [
    ["Total", report.total, ""],
    ["Passed", summary.passed, "passed"],
    ["Failed", summary.failed, "failed"],
    ["Skipped", summary.skipped, "skipped"],
    ["Unexecuted", summary.unexecuted, "unexecuted"],
  ];

  return (
    <section className="panel content-panel results">
      <div className="result-toolbar">
        <div>
          <h2>Execution dashboard</h2>
          <p className="muted result-subtitle">
            {report.requirement.id} · {report.total} planned cases · {report.requirement.text}
          </p>
        </div>
        <div className="download-row">
          <button
            className="subtle-button"
            onClick={() => downloadFile(
              `req2test-${report.requirement.id}.md`,
              result.report_markdown,
              "text/markdown",
            )}
          >Report .md</button>
          <button
            className="subtle-button"
            onClick={() => downloadFile(
              `req2test-${report.requirement.id}.json`,
              JSON.stringify(report, null, 2),
              "application/json",
            )}
          >Report .json</button>
          <button
            className="subtle-button"
            onClick={() => downloadFile(
              `req2test-${report.requirement.id}.py`,
              result.test_source,
              "text/x-python",
            )}
          >Tests .py</button>
        </div>
      </div>
      <div className="stage-row">
        {STAGES.map((stage) => (
          <span className={`stage-pill ${report.stages[stage] ? "" : "pending"}`} key={stage}>
            {report.stages[stage] ? "✓" : "○"} {stage}
          </span>
        ))}
      </div>
      <div className="metrics">
        {metrics.map(([label, value, kind]) => (
          <div className={`metric ${kind}`} key={label}>
            <span>{label}</span><strong>{value}</strong>
          </div>
        ))}
      </div>
      <div className="tabs">
        {[
          ["cases", "Test cases"],
          ["code", "Generated code"],
          ["markdown", "Markdown report"],
        ].map(([id, label]) => (
          <button
            className={`tab ${tab === id ? "active" : ""}`}
            key={id}
            onClick={() => setTab(id)}
          >{label}</button>
        ))}
      </div>
      {tab === "cases" && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>ID</th><th>Scenario</th><th>Category</th><th>Status</th><th>Traceability / evidence</th></tr>
            </thead>
            <tbody>
              {report.cases.map((row) => (
                <tr key={row.id}>
                  <td>{row.id}</td>
                  <td>{row.title}<br /><span className="muted">{row.detail}</span></td>
                  <td>{row.category}</td>
                  <td><span className={`status status-${row.status}`}>{row.status}</span></td>
                  <td>
                    {row.rules.join(", ")}
                    {row.status === "failed" && (
                      <details>
                        <summary>Failure evidence</summary>
                        <pre>{row.detail}</pre>
                      </details>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {tab === "code" && <pre>{result.test_source || "# No tests were approved for generation."}</pre>}
      {tab === "markdown" && <pre>{result.report_markdown}</pre>}
    </section>
  );
}

function LoginPage({ onAuthenticated, initialError = "" }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(initialError);
  const [busy, setBusy] = useState(false);
  const isRegister = mode === "register";

  async function submit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = await postJson(isRegister ? "/api/register" : "/api/login", {
        username,
        password,
      });
      onAuthenticated(data.user);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-screen">
      <section className="auth-card panel">
        <div className="brand auth-brand">
          <div className="brand-mark">R</div>
          <div><strong>Req2Test</strong><small>Autonomous QA pipeline</small></div>
        </div>
        <div className="eyebrow">Private testing workspace</div>
        <h1>{isRegister ? "Create your account." : "Welcome back."}</h1>
        <p className="auth-description">
          {isRegister
            ? "Create an account to keep your generated scenarios and execution reports private."
            : "Sign in to access your requirements, test scenarios, and saved reports."}
        </p>
        <form className="auth-form" onSubmit={submit}>
          <label htmlFor="authUsername">Username</label>
          <input
            id="authUsername"
            autoComplete="username"
            required
            minLength={3}
            maxLength={32}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="e.g. qa_tester"
            title="3–32 letters, numbers, dots, dashes, or underscores"
          />
          <label htmlFor="authPassword">Password</label>
          <input
            id="authPassword"
            type="password"
            autoComplete={isRegister ? "new-password" : "current-password"}
            required
            minLength={isRegister ? 12 : undefined}
            maxLength={256}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder={isRegister ? "At least 12 characters" : "Your password"}
          />
          {isRegister && <p className="field-hint">Use 12–256 characters. Choose a unique username.</p>}
          {error && <div className="error" role="alert">{error}</div>}
          <button className="primary-button auth-submit" disabled={busy}>
            {busy ? "Please wait..." : isRegister ? "Create account" : "Sign in"}
          </button>
        </form>
        <p className="auth-switch">
          {isRegister ? "Already have an account?" : "New to Req2Test?"}{" "}
          <button
            type="button"
            onClick={() => { setError(""); setMode(isRegister ? "login" : "register"); }}
          >{isRegister ? "Sign in" : "Create account"}</button>
        </p>
        <p className="auth-local">Local app · Passwords are stored as salted hashes</p>
      </section>
    </main>
  );
}

function ScenarioLibrary({ plan, history, selected, setSelected, toggleAll, onRun }) {
  return (
    <div className="scenario-page">
      {plan ? (
        <>
          <AnalysisMap plan={plan} />
          <ScenarioReview
            plan={plan}
            selected={selected}
            setSelected={setSelected}
            toggleAll={toggleAll}
          />
          <div className="panel content-panel run-controls scenario-run-controls">
            <div>
              <h2>Generate approved scenarios</h2>
              <p className="section-copy">Choose whether to execute the generated tests against the selected demo target.</p>
            </div>
            <label className="check-control">
              <input type="checkbox" checked={onRun.execute} onChange={(event) => onRun.setExecute(event.target.checked)} />
              Execute generated tests after approval
            </label>
            <label className="target-label" htmlFor="targetSelect">Test target</label>
            <select id="targetSelect" value={onRun.target} onChange={(event) => onRun.setTarget(event.target.value)}>
              <option value="req2test.demo_target.auth_service">Demo target — correct behavior</option>
              <option value="req2test.demo_target.buggy_service">Demo target — contains a bug</option>
            </select>
            <button className="primary-button" onClick={onRun.generate} disabled={onRun.busy}>
              {onRun.busy ? "Generating and running..." : "Generate approved tests →"}
            </button>
            {onRun.error && <div className="error" role="alert">{onRun.error}</div>}
          </div>
        </>
      ) : (
        <div className="panel empty-state">
          <h2>No test scenarios yet</h2>
          <p>Analyze a requirement in the Requirement pipeline tab. Your saved scenarios from previous runs will appear below.</p>
        </div>
      )}
      <section className="panel content-panel history-panel">
        <div className="section-head">
          <div><h2>Your saved scenario sets</h2><p>Scenario sets saved with your previous execution reports.</p></div>
          <span className="chip">{history.length} saved</span>
        </div>
        {history.length ? (
          <div className="history-list">
            {history.map((run) => (
              <article className="history-card" key={run.id}>
                <div>
                  <strong>{run.requirement.text}</strong>
                  <small>{new Date(run.created_at).toLocaleString()} · {run.total} cases · {run.summary.passed} passed · {run.summary.failed} failed</small>
                </div>
                <span className="status status-unexecuted">{run.requirement.id}</span>
              </article>
            ))}
          </div>
        ) : <p className="empty-copy">Completed test runs will be saved here for your account.</p>}
      </section>
    </div>
  );
}

function ExecutionReports({ currentResult, history, openReport }) {
  return (
    <div className="reports-page">
      {currentResult && <ResultDashboard result={currentResult} />}
      <section className="panel content-panel history-panel">
        <div className="section-head">
          <div><h2>Saved execution reports</h2><p>Only your reports are visible in this account.</p></div>
          <span className="chip">{history.length} reports</span>
        </div>
        {history.length ? (
          <div className="history-list">
            {history.map((run) => (
              <article className="history-card" key={run.id}>
                <div>
                  <strong>{run.requirement.text}</strong>
                  <small>{new Date(run.created_at).toLocaleString()} · {run.total} cases · {run.summary.passed} passed · {run.summary.failed} failed · {run.summary.unexecuted} unexecuted</small>
                </div>
                <button className="subtle-button" onClick={() => openReport(run.id)}>View report</button>
              </article>
            ))}
          </div>
        ) : <p className="empty-copy">Run approved tests to save your first execution report.</p>}
      </section>
    </div>
  );
}

function App() {
  const [requirement, setRequirement] = useState(EXAMPLE);
  const [fileName, setFileName] = useState("");
  const [user, setUser] = useState(null);
  const [authReady, setAuthReady] = useState(false);
  const [authError, setAuthError] = useState("");
  const [history, setHistory] = useState([]);
  const [view, setView] = useState("pipeline");
  const [plan, setPlan] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [execute, setExecute] = useState(true);
  const [target, setTarget] = useState("req2test.demo_target.auth_service");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [step, setStep] = useState(1);

  async function refreshHistory() {
    const data = await getJson("/api/history");
    setHistory(data.runs);
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await getJson("/api/session");
        if (!active) return;
        if (data.user) {
          setUser(data.user);
          const saved = await getJson("/api/history");
          if (active) setHistory(saved.runs);
        }
      } catch {
        if (active) {
          setUser(null);
          setAuthError("Could not verify the current session. Please sign in again.");
        }
      } finally {
        if (active) setAuthReady(true);
      }
    })();
    return () => { active = false; };
  }, []);

  async function acceptAuthentication(authenticatedUser) {
    setUser(authenticatedUser);
    setView("pipeline");
    try {
      await refreshHistory();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function signOut() {
    try {
      await postJson("/api/logout", {});
    } finally {
      setUser(null);
      setHistory([]);
      setPlan(null);
      setResult(null);
      setSelected(new Set());
      setView("pipeline");
    }
  }

  async function analyzeRequirement() {
    setError("");
    setBusy("analyze");
    setStep(2);
    setResult(null);
    try {
      const data = await postJson("/api/plan", { text: requirement });
      setPlan(data);
      setSelected(new Set(data.cases.filter((testCase) => testCase.executable).map((testCase) => testCase.id)));
      setStep(3);
      setView("scenarios");
      requestAnimationFrame(() => document.getElementById("planning")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (requestError) {
      setStep(1);
      setError(requestError.message);
    } finally {
      setBusy("");
    }
  }

  async function generateTests() {
    setError("");
    setBusy("run");
    setStep(4);
    try {
      const data = await postJson("/api/run", {
        text: requirement,
        approved_case_ids: [...selected],
        execute,
        target,
      });
      setResult(data);
      await refreshHistory();
      setStep(5);
      setView("reports");
      requestAnimationFrame(() => document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (requestError) {
      setStep(3);
      setError(requestError.message);
    } finally {
      setBusy("");
    }
  }

  async function openReport(runId) {
    setError("");
    try {
      const saved = await getJson(`/api/history/${encodeURIComponent(runId)}`);
      setResult(saved);
      setView("reports");
      setStep(5);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function loadFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError("");
    if (file.size > 100_000) {
      setError("Requirement file must be 100 KB or smaller.");
      event.target.value = "";
      return;
    }
    try {
      setRequirement(await file.text());
      setFileName(file.name);
    } catch {
      setError("Could not read this file. Please use a plain-text .txt or .md file.");
    }
  }

  function toggleAll() {
    const available = plan.cases.filter((testCase) => testCase.executable);
    setSelected(selected.size === available.length
      ? new Set()
      : new Set(available.map((testCase) => testCase.id)));
  }

  if (!authReady) {
    return <main className="auth-screen"><p className="muted">Loading your Req2Test workspace...</p></main>;
  }
  if (!user) {
    return <LoginPage onAuthenticated={acceptAuthentication} initialError={authError} />;
  }

  const navItems = [
    ["pipeline", "⌘", "Requirement pipeline"],
    ["scenarios", "✓", "Test scenarios"],
    ["reports", "▤", "Execution report"],
  ];

  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <div className="brand-mark">R</div>
          <div><strong>Req2Test</strong><small>Autonomous QA pipeline</small></div>
        </div>
        <div className="nav-label">Workspace</div>
        {navItems.map(([id, icon, label]) => (
          <button
            className={`nav-item ${view === id ? "active" : ""}`}
            key={id}
            onClick={() => setView(id)}
          ><span className="nav-icon">{icon}</span>{label}</button>
        ))}
        <div className="nav-label">Pipeline</div>
        <div className="nav-item"><span className="nav-icon">01</span>Ingest requirement</div>
        <div className="nav-item"><span className="nav-icon">02</span>Analyze &amp; plan</div>
        <div className="nav-item"><span className="nav-icon">03</span>Approve scenarios</div>
        <div className="nav-item"><span className="nav-icon">04</span>Generate &amp; run</div>
        <div className="aside-card">
          <strong>Generation ≠ execution</strong>
          <p>Cases without a supported template, or tests you choose not to run, remain explicitly unexecuted.</p>
        </div>
      </aside>
      <main>
        <div className="topline">
          <div>
            <div className="eyebrow">Autonomous requirement-to-test generation pipeline</div>
            <h1>From requirements to test results.</h1>
            <p className="intro">Turn plain-language product requirements into traceable scenarios, executable tests, and an evidence-backed report.</p>
          </div>
          <div className="user-actions">
            <span className="local-pill">● &nbsp; LOCAL WORKSPACE</span>
            <span className="user-pill">{user.username}</span>
            <button className="subtle-button signout-button" onClick={signOut}>Sign out</button>
          </div>
        </div>
        <nav className="workspace-nav" aria-label="Workspace">
          {navItems.map(([id, icon, label]) => (
            <button
              className={`workspace-nav-item ${view === id ? "active" : ""}`}
              key={id}
              onClick={() => setView(id)}
            ><span>{icon}</span>{label}</button>
          ))}
        </nav>
        {error && <div className="error global-error" role="alert">{error}</div>}

        {view === "pipeline" && (
          <>
            <div className="steps" aria-label="Pipeline steps">
              {["Requirement", "Analyze", "Approve", "Generate & run", "Report"].map((label, index) => (
                <div className={`step ${step === index + 1 ? "active" : ""} ${step > index + 1 ? "done" : ""}`} key={label}>
                  <span className="step-num">{index + 1}</span><span>{label}</span>
                </div>
              ))}
            </div>
            <section className="panel input-panel">
              <div className="section-head">
                <div>
                  <h2>01 / Requirement input</h2>
                  <p>Paste a user story, acceptance criteria, or plain-language specification.</p>
                </div>
                <button className="example-button" onClick={() => setRequirement(EXAMPLE)}>Load example ↗</button>
              </div>
              <textarea
                value={requirement}
                maxLength={100_000}
                onChange={(event) => setRequirement(event.target.value)}
                placeholder="Describe the behavior you want to test..."
              />
              <div className="input-footer">
                <div>
                  <label className="upload-label">
                    ＋ Upload a .txt or .md requirement
                    <input type="file" accept=".txt,.md,text/plain,text/markdown" onChange={loadFile} />
                  </label>
                  {fileName && <span className="muted file-name">{fileName}</span>}
                </div>
                <button className="primary-button" onClick={analyzeRequirement} disabled={Boolean(busy)}>
                  {busy === "analyze" ? "Analyzing..." : "Analyze requirement →"}
                </button>
              </div>
            </section>
            {plan && <AnalysisMap plan={plan} />}
          </>
        )}

        {view === "scenarios" && (
          <ScenarioLibrary
            plan={plan}
            history={history}
            selected={selected}
            setSelected={setSelected}
            toggleAll={toggleAll}
            onRun={{
              execute,
              setExecute,
              target,
              setTarget,
              busy: busy === "run",
              error,
              generate: generateTests,
            }}
          />
        )}
        {view === "reports" && (
          <ExecutionReports
            currentResult={result}
            history={history}
            openReport={openReport}
          />
        )}
        <div className="footer-note">Private workspace for {user.username} · Local app · No external services</div>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
