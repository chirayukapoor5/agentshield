'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

type Event = { id: number; event_id: string; tool: string; reason: string; allowed: boolean; created_at: string };
type Incident = { id: number; tool: string; denial_count: number; severity: string; status: string; updated_at: string };
type Overview = { events: Event[]; incidents: Incident[]; scope: string };
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const TOKEN_KEY = 'agentshield_access_token';

export default function SecurityMonitoring() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const refresh = useCallback(async () => {
    const token = window.localStorage.getItem(TOKEN_KEY);
    if (!token) { setError('Sign in on the main AgentShield dashboard first.'); return; }
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/v1/security/overview`, {
        headers: { Authorization: `Bearer ${token}` }, cache: 'no-store'
      });
      if (!response.ok) throw new Error(`Security API returned ${response.status}`);
      setData(await response.json() as Overview);
      setError('');
    } catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  async function changeStatus(id: number, status: string) {
    const token = window.localStorage.getItem(TOKEN_KEY);
    if (!token) { setError('Authentication required'); return; }
    try {
      const response = await fetch(`${API_URL}/api/v1/security/incidents/${id}`, {
        method: 'PATCH', headers: {
          Authorization: `Bearer ${token}`, 'Content-Type': 'application/json'
        }, body: JSON.stringify({ status })
      });
      if (!response.ok) throw new Error(`Status update failed: ${response.status}`);
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : 'Update failed'); }
  }

  return <main style={{ maxWidth: 1100, margin: '3rem auto', padding: '0 1rem', fontFamily: 'system-ui' }}>
    <Link href="/">← Main dashboard</Link>
    <h1>AgentShield Security Operations</h1>
    <p>Authenticated, organization-scoped monitoring. Event data is limited to metadata; no raw prompts or arguments.</p>
    <button onClick={() => void refresh()} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</button>
    {error && <p role="alert" style={{ color: 'crimson' }}>{error}</p>}
    <h2>Incidents ({data?.incidents.length ?? 0})</h2>
    <div style={{ overflowX: 'auto' }}><table cellPadding={12}>
      <thead><tr><th>Tool</th><th>Severity</th><th>Denials</th><th>Status</th><th>Action</th></tr></thead>
      <tbody>{data?.incidents.map(i => <tr key={i.id}>
        <td>{i.tool}</td><td>{i.severity}</td><td>{i.denial_count}</td><td>{i.status}</td>
        <td><select aria-label={`Status for ${i.tool}`} value={i.status}
          onChange={e => void changeStatus(i.id, e.target.value)}>
          <option value="open">Open</option><option value="investigating">Investigating</option>
          <option value="resolved">Resolved</option>
        </select></td>
      </tr>)}</tbody>
    </table></div>
    <h2>Recent security events ({data?.events.length ?? 0})</h2>
    <div style={{ overflowX: 'auto' }}><table cellPadding={12}>
      <thead><tr><th>Time (UTC)</th><th>Tool</th><th>Decision</th><th>Reason</th></tr></thead>
      <tbody>{data?.events.map(e => <tr key={e.id}>
        <td>{e.created_at}</td><td>{e.tool}</td>
        <td>{e.allowed ? 'Allowed' : 'Denied'}</td><td>{e.reason}</td>
      </tr>)}</tbody>
    </table></div>
    <p>Displays up to 100 events and incidents per request. This is not a production SIEM.</p>
  </main>;
}
