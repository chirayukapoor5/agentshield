'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import './lab.css';

type Scenario = {
  id: string;
  label: string;
  category: string;
  tool: string;
  args: string;
  intent: string;
  rationale: string;
  expected: 'allow' | 'deny';
  reason: string;
};

const scenarios: Scenario[] = [
  {
    id: 'read', label: 'Read a document', category: 'Authorized',
    tool: 'read_document', args: '{ "id": "synthetic-1" }',
    intent: 'The user asks the assistant to read a permitted synthetic document.',
    rationale: 'The tool is explicitly on the read-only allowlist.',
    expected: 'allow', reason: 'allowlisted'
  },
  {
    id: 'email', label: 'Send an email without approval', category: 'Blocked',
    tool: 'send_email', args: '{ "to": "test@example.org" }',
    intent: 'A tool output tries to trigger a message the user has not approved.',
    rationale: 'Sending an email requires an approval callback, which is absent.',
    expected: 'deny', reason: 'approval_not_configured'
  },
  {
    id: 'delete', label: 'Delete a file without approval', category: 'Blocked',
    tool: 'delete_file', args: '{ "path": "synthetic.txt" }',
    intent: 'An agent attempts a state-changing action without explicit approval.',
    rationale: 'File deletion is approval-gated; approval has not been provided.',
    expected: 'deny', reason: 'approval_not_configured'
  },
  {
    id: 'shell', label: 'Invoke an unregistered tool', category: 'Blocked',
    tool: 'execute_shell', args: '{ "command": "echo demo" }',
    intent: 'A lower-trust message asks the agent to use a tool absent from policy.',
    rationale: 'The tool is not on any allowlist.',
    expected: 'deny', reason: 'tool_not_allowlisted'
  },
  {
    id: 'https', label: 'Fetch an approved HTTPS URL', category: 'Authorized',
    tool: 'fetch_url', args: '{ "url": "https://docs.example.org/guide" }',
    intent: 'The agent retrieves an approved synthetic documentation URL.',
    rationale: 'HTTPS and exact configured hostname both match.',
    expected: 'allow', reason: 'allowlisted'
  },
  {
    id: 'host', label: 'Fetch an unapproved hostname', category: 'Blocked',
    tool: 'fetch_url', args: '{ "url": "https://unlisted.example.org/guide" }',
    intent: 'An agent attempts outbound access to a hostname not configured by the developer.',
    rationale: 'Hostname not present in the exact allowlist.',
    expected: 'deny', reason: 'destination_not_allowlisted'
  },
  {
    id: 'http', label: 'Use an insecure URL', category: 'Blocked',
    tool: 'fetch_url', args: '{ "url": "http://docs.example.org/guide" }',
    intent: 'A tool call requests a non-HTTPS destination.',
    rationale: 'The configured URL rule requires HTTPS.',
    expected: 'deny', reason: 'destination_not_allowlisted'
  },
  {
    id: 'lookalike', label: 'Use a lookalike hostname', category: 'Blocked',
    tool: 'fetch_url', args: '{ "url": "https://docs.example.org.evil.test" }',
    intent: 'A deceptive hostname mimics the approved domain.',
    rationale: 'Exact hostname matching rejects the lookalike.',
    expected: 'deny', reason: 'destination_not_allowlisted'
  }
];

const REPO = 'https://github.com/chirayukapoor5/agentshield';
const evidence = [
  { label: 'SDK tests', value: '13 passed', sub: 'Python 3.10 + 3.12 CI', url: `${REPO}/actions/runs/42050659963` },
  { label: 'Groq API', value: '20 / 20', sub: 'Connectivity requests succeeded', url: `${REPO}/actions/runs/42050250859` },
  { label: 'HTTP 429', value: '0', sub: 'In the 20-call smoke test', url: `${REPO}/blob/research/multilingual-injection-2026/docs/GROQ_PREFLIGHT_RESULTS.md` },
  { label: 'Policy demo', value: '8 / 8', sub: 'Expected scripted decisions matched', url: `${REPO}/blob/research/multilingual-injection-2026/docs/SDK_DEMO_RESULTS.md` },
];

export default function LabPage() {
  const [selected, setSelected] = useState(1);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [history, setHistory] = useState<number[]>([]);
  const [showRecording, setShowRecording] = useState(false);
  const [protectionEnabled, setProtectionEnabled] = useState(true);
  const item = scenarios[selected];
  const decision = protectionEnabled ? item.expected : 'unprotected';

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setStep(current => {
        if (current >= 3) {
          setPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, 1100);
    return () => window.clearInterval(timer);
  }, [playing]);

  useEffect(() => {
    if (step === 3 && protectionEnabled) {
      setHistory(old => old.includes(selected) ? old : [...old, selected]);
    }
  }, [step, selected, protectionEnabled]);

  const completed = useMemo(() => scenarios.filter((_, i) => history.includes(i)), [history]);
  const allowedCount = completed.filter(x => x.expected === 'allow').length;
  const deniedCount = completed.filter(x => x.expected === 'deny').length;

  function pick(index: number) {
    setPlaying(false);
    setStep(0);
    setSelected(index);
  }

  function play() {
    setStep(0);
    setPlaying(true);
  }

  function reset() {
    setPlaying(false);
    setStep(0);
    setSelected(1);
    setHistory([]);
    setProtectionEnabled(true);
  }

  async function copyShare() {
    if (!navigator.clipboard) return;
    await navigator.clipboard.writeText(window.location.href);
    setShowRecording(true);
  }

  return (
    <main className="lab">
      <div className="lab-orb lab-orb-a" aria-hidden="true" />
      <div className="lab-orb lab-orb-b" aria-hidden="true" />
      <div className="lab-container">
        <nav className="lab-nav" aria-label="Primary navigation">
          <Link href="/" className="lab-brand">
            <span className="lab-logo">◇</span>
            <span>AGENT<span className="lab-accent">SHIELD</span></span>
            <span className="lab-brand-tag">LAB</span>
          </Link>
          <div className="lab-nav-links">
            <a href="#simulation">Simulation</a>
            <a href="#proof">Verified proof</a>
            <a href="#integration">SDK</a>
            <a href={REPO} target="_blank" rel="noreferrer">GitHub ↗</a>
          </div>
        </nav>

        <section className="lab-hero">
          <div className="lab-hero-copy">
            <p className="lab-kicker"><span className="lab-live-dot" /> OPEN-SOURCE SECURITY RESEARCH · PROTOTYPE</p>
            <h1>Stop unsafe tool calls<br /><span className="lab-gradient">before they execute.</span></h1>
            <p className="lab-lead">A Python policy gate for tool-using AI agents. See how unauthorized email, file deletion, and outbound requests are denied before the wrapped tool executes—then inspect the code.</p>
            <div className="lab-actions">
              <a href="#simulation" className="lab-btn lab-btn-primary">▶ Compare guarded vs unguarded</a>
              <a href="#integration" className="lab-btn lab-btn-ghost">View 10-line integration ↗</a>
            </div>
            <p className="lab-disclaimer"><strong>Demonstration only.</strong> This is a deterministic browser replay of the SDK test scenarios—not a live LLM, a penetration test, or a measured prompt-injection defense rate.</p>
          </div>
          <div className="lab-hero-art" aria-hidden="true">
            <div className="lab-art-ring lab-art-ring-one" />
            <div className="lab-art-ring lab-art-ring-two" />
            <div className="lab-art-core"><span>◇</span><strong>AGENTSHIELD</strong><small>POLICY ENGINE · v0.1</small></div>
            <span className="lab-art-pill lab-art-pill-one">✓ Approved tool</span>
            <span className="lab-art-pill lab-art-pill-two">× Blocked action</span>
            <span className="lab-art-pill lab-art-pill-three">◉ Audit event</span>
          </div>
        </section>

        <section className="lab-proof" id="proof" aria-label="Evidence-backed project metrics">
          <div className="lab-section-top"><div><p className="lab-eyebrow">ENGINEERING EVIDENCE</p><h2>Real tests. Clear boundaries.</h2></div><span className="lab-source-label">Verified November 5, 2026</span></div>
          <div className="lab-proof-grid">
            {evidence.map(metric => (
              <a key={metric.label} href={metric.url} target="_blank" rel="noreferrer" className="lab-proof-card">
                <span className="lab-card-label">{metric.label} <span>↗</span></span>
                <strong>{metric.value}</strong>
                <small>{metric.sub}</small>
              </a>
            ))}
          </div>
          <p className="lab-evidence-note">The first three cards describe SDK CI or real API connectivity; the policy-demo card describes eight scripted scenarios. None measures adversarial AgentDojo ASR, benign utility, or production protection.</p>
        </section>

        <section className="lab-simulation" id="simulation">
          <div className="lab-section-top">
            <div><p className="lab-eyebrow">INTERACTIVE SANDBOX</p><h2>Watch the policy decision.</h2><p>Choose a scenario to replay the SDK&apos;s documented decision logic.</p></div>
            <span className="lab-demo-flag"><span /> SYNTHETIC · OFFLINE · NO REAL TOOL EXECUTION</span>
          </div>
          <div className="lab-comparison" role="group" aria-label="Protection mode">
            <div><strong>See the difference</strong><p>Switch enforcement off to illustrate the risk of executing an unguarded tool request. This is a conceptual comparison, not an LLM attack result.</p></div>
            <div className="lab-mode-switch">
              <button type="button" aria-pressed={!protectionEnabled} className={!protectionEnabled ? 'lab-mode-active lab-mode-unsafe' : ''} onClick={() => {setPlaying(false);setStep(0);setProtectionEnabled(false);}}>Without guard</button>
              <button type="button" aria-pressed={protectionEnabled} className={protectionEnabled ? 'lab-mode-active' : ''} onClick={() => {setPlaying(false);setStep(0);setProtectionEnabled(true);}}>With AgentShield</button>
            </div>
          </div>
          <div className="lab-sim-grid">
            <aside className="lab-sim-menu" aria-label="Simulation scenarios">
              <div className="lab-menu-heading"><span>SCENARIO LIBRARY</span><span>08</span></div>
              {scenarios.map((scenario, index) => (
                <button type="button" key={scenario.id} onClick={() => pick(index)}
                  className={`lab-scenario ${index === selected ? 'lab-scenario-active' : ''}`}
                  aria-pressed={index === selected}>
                  <span className="lab-scenario-index">{String(index + 1).padStart(2, '0')}</span>
                  <span className="lab-scenario-name">{scenario.label}<small>{scenario.category}</small></span>
                  <span className={`lab-scenario-outcome ${scenario.expected === 'allow' ? 'lab-green' : 'lab-red'}`}>{scenario.expected === 'allow' ? '✓' : '×'}</span>
                </button>
              ))}
            </aside>
            <div className="lab-sim-main">
              <div className="lab-terminal">
                <div className="lab-terminal-bar"><div className="lab-dots"><i /><i /><i /></div><span>agent-runtime / simulation.log</span><span className="lab-terminal-mode">REPLAY</span></div>
                <div className="lab-terminal-body" role="status" aria-live="polite">
                  <div className="lab-term-line"><span className="lab-term-time">00:00</span><span className="lab-term-key">USER INTENT</span><span>{item.intent}</span></div>
                  {step >= 1 && <div className="lab-term-line"><span className="lab-term-time">00:01</span><span className="lab-term-key">TOOL REQUEST</span><span><code>{item.tool}</code> <code>{item.args}</code></span></div>}
                  {step >= 2 && <div className="lab-term-line"><span className="lab-term-time">00:02</span><span className="lab-term-key">POLICY CHECK</span><span>{protectionEnabled ? item.rationale : "No AgentShield wrapper is registered. The tool request would bypass this policy gate; downstream execution depends on the host application."}</span></div>}
                  {step >= 3 && <div className="lab-term-line"><span className="lab-term-time">00:03</span><span className="lab-term-key">DECISION</span><span className={decision === 'allow' ? 'lab-green' : 'lab-red'}><strong>{decision === 'unprotected' ? 'NO POLICY ENFORCEMENT' : decision.toUpperCase()}</strong> · {decision === 'unprotected' ? 'unguarded_tool_path' : item.reason}</span></div>}
                  {step === 0 && <div className="lab-term-idle">▌ Select Run simulation to replay four steps…</div>}
                </div>
                <div className="lab-terminal-footer"><span><span className="lab-live-dot" /> ISOLATED BROWSER SIMULATION</span><span>{protectionEnabled ? "GUARDED" : "UNGUARDED"} · STEP {step}/3</span></div>
              </div>
              <div className="lab-sim-controls">
                <button type="button" onClick={play} className="lab-btn lab-btn-primary">{playing ? '↻ Restart replay' : '▶ Run simulation'}</button>
                <button type="button" className="lab-btn lab-btn-ghost" onClick={() => { setPlaying(false); setStep(3); }}>Skip to decision</button>
                <button type="button" className="lab-reset" onClick={reset}>Reset</button>
              </div>
              <div className="lab-run-summary">
                <div><small>GUARDED REPLAYS</small><strong>{completed.length} / 8</strong></div>
                <div><small>ALLOWED</small><strong className="lab-green">{allowedCount}</strong></div>
                <div><small>DENIED</small><strong className="lab-red">{deniedCount}</strong></div>
                <div><small>REAL API CALLS</small><strong>0</strong></div>
              </div>
            </div>
          </div>
        </section>

        <section className="lab-integration" id="integration">
          <div className="lab-integration-text"><p className="lab-eyebrow">DEVELOPER EXPERIENCE</p><h2>One package.<br /><span className="lab-gradient">Explicit control.</span></h2><p>Guard the tool registry your agent actually uses. Calls that bypass the wrapped registry are outside the enforcement boundary.</p>
            <a className="lab-inline-link" href={`${REPO}/tree/research/multilingual-injection-2026/sdk`} target="_blank" rel="noreferrer">Explore SDK source ↗</a>
          </div>
          <div className="lab-code"><div className="lab-terminal-bar"><div className="lab-dots"><i /><i /><i /></div><span>quickstart.py</span><span>PYTHON</span></div><pre>{`# Install directly from the repository checkout
$ pip install ./sdk

from agentshield_guard import AgentShield, ToolPolicy

shield = AgentShield(
    ToolPolicy(
        read_only_tools=frozenset({"search"}),
        approval_tools=frozenset({"send_email"}),
    )
)

# Register these wrappers, NOT the raw tools.
secured_tools = shield.wrap_registry({
    "search": my_search_function,
    "send_email": my_email_function,
})`}</pre></div>
        </section>

        <section className="lab-roadmap">
          <p className="lab-eyebrow">HONEST RESEARCH STATUS</p>
          <h2>Built, tested, and still in progress.</h2>
          <div className="lab-roadmap-grid">
            <div><span className="lab-status lab-status-pass">✓ VERIFIED</span><h3>Tool policy SDK</h3><p>13 CI tests passed. Eight synthetic decisions reproduced with traceable inputs.</p></div>
            <div><span className="lab-status lab-status-pass">✓ VERIFIED</span><h3>Real API connectivity</h3><p>20/20 Groq requests succeeded in a capped smoke test. No 429 responses.</p></div>
            <div><span className="lab-status lab-status-pending">◷ IN PROGRESS</span><h3>Multilingual AgentDojo</h3><p>Benchmark integration checks passed; attack-success and utility evaluations not yet run.</p></div>
            <div><span className="lab-status lab-status-pending">◷ NOT RELEASED</span><h3>Production protection</h3><p>No automatic cross-framework interception, production approval service, or guarantee of comprehensive safety.</p></div>
          </div>
        </section>

        <section className="lab-share">
          <div><p className="lab-eyebrow">SHOW THE WORK</p><h2>Record a walkthrough.</h2><p>Try guarded vs unguarded mode, then tell us which agent framework you use and what dangerous tool action you need to control. No signup required.</p></div>
          <div className="lab-share-actions">
            <button type="button" className="lab-btn lab-btn-primary" onClick={copyShare}>{showRecording ? '✓ Page link copied' : 'Copy demo link'}</button>
            <a href={`${REPO}/issues/new?title=AgentShield%20developer%20feedback&body=My%20agent%20framework%3A%20%0AThe%20tool%20action%20I%20need%20to%20guard%3A%20%0AMy%20biggest%20integration%20blocker%3A%20`} target="_blank" rel="noreferrer" className="lab-btn lab-btn-ghost">Request an integration / give feedback ↗</a>
          </div>
        </section>
        <footer className="lab-footer"><span>◇ AGENTSHIELD LAB · EXPERIMENTAL OPEN-SOURCE DEMO</span><span>Not a security certification. No production claims. <Link href="/">Workspace dashboard →</Link></span></footer>
      </div>
    </main>
  );
}
