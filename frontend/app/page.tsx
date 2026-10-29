'use client';

import { FormEvent, useCallback, useEffect, useState } from 'react';

type User = {
  id: number;
  email: string;
  full_name: string;
};

type Website = {
  id: number;
  name: string;
  url: string;
  status: string;
  owner_verified: boolean;
  verification_status: string;
  verified_at: string | null;
};

type WebsiteCreated = Website & {
  verification_token: string;
  verification_dns_name: string;
  verification_instructions: string;
};

type ScanCheck = {
  id: string;
  label: string;
  status: 'passed' | 'finding' | 'unavailable';
  evidence: string;
  reason?: string;
};

type Scan = {
  id: number;
  status: string;
  scanner_version: string;
  compatibility_score: number | null;
  security_score: number | null;
  score_coverage: {
    compatibility?: { checked: number; total: number };
    security?: { checked: number; total: number };
  };
  checks: ScanCheck[];
  summary: string;
  started_at: string;
  finished_at: string | null;
};

type VerificationInstructions = {
  instructions: string;
};

type Agent = {
  id: number;
  name: string;
  is_active: boolean;
};

type Finding = {
  id: number;
  website_id: number;
  scan_id: number;
  title: string;
  severity: string;
  evidence: string;
  affected_url: string | null;
  confidence: string;
  verification_status: string;
  detected_at: string | null;
};

type AuditEvent = {
  id: number;
  event_type: string;
  resource_type: string;
  resource_id: string | null;
  created_at: string;
};

type DashboardData = {
  websites: Website[];
  agents: Agent[];
  findings: Finding[];
  activity: AuditEvent[];
  latestScans: Record<number, Scan | null>;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const TOKEN_KEY = 'agentshield_access_token';

async function request<T>(path: string, token: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}/api/v1${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === 'string') {
        message = body.detail;
      }
    } catch {
      // Keep the HTTP status message when the server does not return JSON.
    }
    throw new Error(`${response.status}: ${message}`);
  }

  return response.json() as Promise<T>;
}

async function loadDashboard(token: string): Promise<DashboardData> {
  const [websites, agents, activity] = await Promise.all([
    request<Website[]>('/websites', token),
    request<Agent[]>('/agents', token),
    request<AuditEvent[]>('/audit-events', token),
  ]);
  const [findingsByWebsite, scansByWebsite] = await Promise.all([
    Promise.all(websites.map((website) => request<Finding[]>(`/websites/${website.id}/findings`, token))),
    Promise.all(websites.map((website) => request<Scan[]>(`/websites/${website.id}/scans`, token))),
  ]);

  return {
    websites,
    agents,
    findings: findingsByWebsite.flat(),
    activity: activity.slice(0, 5),
    latestScans: Object.fromEntries(
      websites.map((website, index) => [website.id, scansByWebsite[index][0] ?? null]),
    ),
  };
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

export default function Page() {
  const [user, setUser] = useState<User | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [websiteName, setWebsiteName] = useState('');
  const [websiteUrl, setWebsiteUrl] = useState('');
  const [verificationMessage, setVerificationMessage] = useState('');
  const [busyWebsiteId, setBusyWebsiteId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const refreshDashboard = useCallback(async (accessToken: string) => {
    setError('');
    try {
      const data = await loadDashboard(accessToken);
      setDashboard(data);
    } catch (reason) {
      if (reason instanceof Error && reason.message.startsWith('401:')) {
        sessionStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setUser(null);
      }
      setError(reason instanceof Error ? reason.message : 'Unable to load dashboard data.');
    }
  }, []);

  useEffect(() => {
    const savedToken = sessionStorage.getItem(TOKEN_KEY);
    if (!savedToken) {
      setLoading(false);
      return;
    }

    setToken(savedToken);
    Promise.all([
      request<User>('/auth/me', savedToken),
      loadDashboard(savedToken),
    ])
      .then(([currentUser, data]) => {
        setUser(currentUser);
        setDashboard(data);
      })
      .catch((reason: unknown) => {
        sessionStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setError(reason instanceof Error ? reason.message : 'Unable to connect to AgentShield API.');
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError('');

    try {
      const response = await fetch(`${API_URL}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username: email, password }),
      });
      if (!response.ok) {
        throw new Error(response.status === 401 ? 'Email or password is incorrect.' : `Sign-in failed (${response.status}).`);
      }

      const result: { access_token: string } = await response.json();
      sessionStorage.setItem(TOKEN_KEY, result.access_token);
      const [currentUser, data] = await Promise.all([
        request<User>('/auth/me', result.access_token),
        loadDashboard(result.access_token),
      ]);
      setToken(result.access_token);
      setUser(currentUser);
      setDashboard(data);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to sign in.');
    } finally {
      setSubmitting(false);
      setLoading(false);
    }
  }

  async function handleAddWebsite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    setSubmitting(true);
    setError('');
    try {
      const created = await request<WebsiteCreated>('/websites', token, {
        method: 'POST',
        body: JSON.stringify({ name: websiteName, url: websiteUrl }),
      });
      setVerificationMessage(created.verification_instructions);
      setWebsiteName('');
      setWebsiteUrl('');
      await refreshDashboard(token);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to add website.');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleWebsiteAction(website: Website, action: 'issue' | 'verify' | 'scan') {
    if (!token) return;
    setBusyWebsiteId(website.id);
    setError('');
    setVerificationMessage('');
    try {
      if (action === 'issue') {
        const instructions = await request<VerificationInstructions>(
          `/websites/${website.id}/verification`,
          token,
          { method: 'POST' },
        );
        setVerificationMessage(instructions.instructions);
      } else if (action === 'verify') {
        await request<Website>(`/websites/${website.id}/verify`, token, { method: 'POST' });
        setVerificationMessage(`Ownership verified for ${website.name}. You can now start a scan.`);
        await refreshDashboard(token);
      } else {
        await request<Scan>(`/websites/${website.id}/scans`, token, { method: 'POST' });
        await refreshDashboard(token);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Website action failed.');
    } finally {
      setBusyWebsiteId(null);
    }
  }

  function handleLogout() {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    setDashboard(null);
    setVerificationMessage('');
    setError('');
  }

  if (loading) {
    return (
      <main className="dashboard-shell">
        <div className="dashboard-content loading-state" role="status">Connecting to AgentShield…</div>
      </main>
    );
  }

  if (!user || !token) {
    return (
      <main className="dashboard-shell">
        <div className="auth-card">
          <div className="brand-lockup">
            <div className="brand-mark" aria-hidden="true">A</div>
            <div>
              <p className="eyebrow">AgentShield</p>
              <h1>Sign in to your workspace</h1>
            </div>
          </div>
          <p className="intro-copy">Use your AgentShield API account to view organization data.</p>
          {error && <p className="error-message" role="alert">{error}</p>}
          <form className="form-stack" onSubmit={handleLogin}>
            <label>
              Email
              <input autoComplete="username" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            </label>
            <label>
              Password
              <input autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
            </label>
            <button className="primary-button" disabled={submitting} type="submit">
              {submitting ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
          <p className="helper-text">
            Local demo: demo@agentshield.local / password123
          </p>
          <p className="helper-text">API: {API_URL}</p>
        </div>
      </main>
    );
  }

  const data = dashboard ?? { websites: [], agents: [], findings: [], activity: [], latestScans: {} };
  const activeAgents = data.agents.filter((agent) => agent.is_active).length;
  const verifiedSites = data.websites.filter((website) => website.owner_verified).length;

  return (
    <main className="dashboard-shell">
      <div className="dashboard-content">
        <header className="topbar">
          <div className="brand-lockup">
            <div className="brand-mark" aria-hidden="true">A</div>
            <div>
              <p className="eyebrow">AgentShield</p>
              <h1>Security overview</h1>
            </div>
          </div>
          <div className="account-actions">
            <span className="account-name">{user.full_name}</span>
            <button className="quiet-button" onClick={handleLogout} type="button">Sign out</button>
          </div>
        </header>

        <section className="intro" aria-labelledby="welcome-title">
          <div>
            <p className="eyebrow">Live workspace data</p>
            <h2 id="welcome-title">AI-agent compatibility and security</h2>
            <p className="intro-copy">Organization records loaded from the AgentShield API.</p>
          </div>
          <p className="sample-notice">
            Scans use safe, non-destructive public checks only. Results are limited to the displayed checks and are not a security certification.
          </p>
        </section>

        {error && <p className="error-message dashboard-error" role="alert">{error}</p>}
        {verificationMessage && <p className="info-message" role="status">{verificationMessage}</p>}

        <section className="metrics-grid" aria-label="Workspace metrics">
          <article className="metric-card">
            <p className="metric-label">Registered websites</p>
            <p className="metric-value">{data.websites.length}</p>
            <p className="metric-change neutral">Stored in this organization</p>
          </article>
          <article className="metric-card">
            <p className="metric-label">DNS ownership verified</p>
            <p className="metric-value">{verifiedSites}</p>
            <p className="metric-change neutral">Verified by DNS TXT challenge</p>
          </article>
          <article className="metric-card">
            <p className="metric-label">Active agents</p>
            <p className="metric-value">{activeAgents}</p>
            <p className="metric-change neutral">Configured identities</p>
          </article>
          <article className="metric-card">
            <p className="metric-label">Scan findings</p>
            <p className="metric-value">{data.findings.length}</p>
            <p className="metric-change neutral">Evidence-backed checks only</p>
          </article>
        </section>

        <div className="details-grid">
          <section className="panel" aria-labelledby="websites-title">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Organization resources</p>
                <h2 id="websites-title">Websites</h2>
              </div>
              <span className="panel-count">{data.websites.length} total</span>
            </div>
            {data.websites.length === 0 ? (
              <p className="empty-state">No websites registered yet. Add one below to get started.</p>
            ) : (
              <ul className="website-list">
                {data.websites.map((website) => {
                  const findingCount = data.findings.filter((finding) => finding.website_id === website.id).length;
                  const latestScan = data.latestScans[website.id];
                  return (
                    <li className="website-entry" key={website.id}>
                      <div className="website-row">
                        <div className="site-identity">
                          <span className="site-icon" aria-hidden="true">{website.name[0]?.toUpperCase() ?? 'W'}</span>
                          <div>
                            <p className="site-name">{website.name}</p>
                            <p className="site-status">{website.url} · DNS ownership {website.verification_status}</p>
                            {website.verified_at && <p className="site-status">Verified {formatDate(website.verified_at)}</p>}
                          </div>
                        </div>
                        <span className="panel-count">{findingCount} findings</span>
                      </div>
                      {latestScan ? (
                        <div className="scan-summary">
                          <p className="site-status">
                            Latest scan: {latestScan.status}
                            {latestScan.finished_at ? ` · ${formatDate(latestScan.finished_at)}` : ''}
                          </p>
                          <p className="scan-score">
                            Security controls: {latestScan.security_score === null ? 'not scored' : `${latestScan.security_score}/100`}
                            {latestScan.score_coverage.security && ` (${latestScan.score_coverage.security.checked}/${latestScan.score_coverage.security.total} checks)`}
                          </p>
                          <p className="scan-score">
                            Compatibility indicators: {latestScan.compatibility_score === null ? 'not scored' : `${latestScan.compatibility_score}/100`}
                            {latestScan.score_coverage.compatibility && ` (${latestScan.score_coverage.compatibility.checked}/${latestScan.score_coverage.compatibility.total} checks)`}
                          </p>
                          <p className="activity-copy">{latestScan.summary}</p>
                          {latestScan.checks.length > 0 && (
                            <details className="scan-checks">
                              <summary>View {latestScan.checks.length} check results</summary>
                              <ul>
                                {latestScan.checks.map((check) => (
                                  <li key={`${latestScan.id}-${check.id}`}>
                                    <strong>{check.label}: {check.status}</strong>
                                    <span>{check.evidence}</span>
                                  </li>
                                ))}
                              </ul>
                            </details>
                          )}
                        </div>
                      ) : (
                        <p className="site-status scan-summary">No scan has been completed.</p>
                      )}
                      <div className="website-actions">
                        {!website.owner_verified && website.verification_status === 'pending' && (
                          <button
                            className="quiet-button"
                            disabled={busyWebsiteId === website.id}
                            onClick={() => handleWebsiteAction(website, 'verify')}
                            type="button"
                          >
                            {busyWebsiteId === website.id ? 'Checking DNS…' : 'Verify DNS record'}
                          </button>
                        )}
                        {!website.owner_verified && website.verification_status !== 'pending' && (
                          <button
                            className="quiet-button"
                            disabled={busyWebsiteId === website.id}
                            onClick={() => handleWebsiteAction(website, 'issue')}
                            type="button"
                          >
                            Request a new DNS token
                          </button>
                        )}
                        {website.owner_verified && (
                          <button
                            className="primary-button"
                            disabled={busyWebsiteId === website.id}
                            onClick={() => handleWebsiteAction(website, 'scan')}
                            type="button"
                          >
                            {busyWebsiteId === website.id ? 'Scanning…' : 'Run safe scan'}
                          </button>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
            <form className="website-form" onSubmit={handleAddWebsite}>
              <h3>Add a website</h3>
              <label>
                Display name
                <input maxLength={255} minLength={2} value={websiteName} onChange={(event) => setWebsiteName(event.target.value)} required />
              </label>
              <label>
                Website URL
                <input type="url" placeholder="https://example.com" value={websiteUrl} onChange={(event) => setWebsiteUrl(event.target.value)} required />
              </label>
              <button className="primary-button" disabled={submitting} type="submit">
                {submitting ? 'Saving…' : 'Add website'}
              </button>
            </form>
          </section>

          <section className="panel" aria-labelledby="findings-title">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Observed evidence</p>
                <h2 id="findings-title">Latest findings</h2>
              </div>
              <span className="panel-count">{data.findings.length} total</span>
            </div>
            {data.findings.length === 0 ? (
              <p className="empty-state">No scan findings recorded. Findings appear only after a verified website is scanned.</p>
            ) : (
              <ul className="activity-list">
                {data.findings.slice(0, 8).map((finding) => (
                  <li className="activity-item" key={finding.id}>
                    <span className="activity-icon warning-icon" aria-hidden="true">!</span>
                    <div>
                      <p className="activity-title">{finding.title} · {finding.severity}</p>
                      <p className="activity-copy">{finding.evidence}</p>
                      {finding.affected_url && <p className="activity-time">{finding.affected_url}</p>}
                      <p className="activity-time">
                        {finding.verification_status} · {finding.confidence} confidence
                        {finding.detected_at ? ` · ${formatDate(finding.detected_at)}` : ''}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="panel" aria-labelledby="activity-title">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Persisted records</p>
                <h2 id="activity-title">Recent audit events</h2>
              </div>
              <span className="panel-count">{data.activity.length} shown</span>
            </div>
            {data.activity.length === 0 ? (
              <p className="empty-state">No audit events have been recorded for this organization.</p>
            ) : (
              <ul className="activity-list">
                {data.activity.map((event) => (
                  <li className="activity-item" key={event.id}>
                    <span className="activity-icon neutral-icon" aria-hidden="true">•</span>
                    <div>
                      <p className="activity-title">{event.event_type}</p>
                      <p className="activity-copy">
                        {event.resource_type}{event.resource_id ? ` · ${event.resource_id}` : ''}
                      </p>
                      <p className="activity-time">{formatDate(event.created_at)}</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
        <footer className="page-footer">
          AgentShield prototype <span aria-hidden="true">·</span> Data loaded from the authenticated API
        </footer>
      </div>
    </main>
  );
}
