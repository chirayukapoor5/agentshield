/**
 * Dependency-free runtime smoke test of the public demo script.
 * Mock DOM; assertions verify UI state, never real tool execution or LLM ASR.
 * Run: node scripts/test_public_demo.mjs
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync('public-demo/index.html', 'utf8');
assert.ok(html.includes('data-demo-version="sandbox-approval-v2"'));
assert.ok(html.includes('src="sandbox.js"'));
const bundled = readFileSync('public-demo/sandbox.js', 'utf8');

class Element {
  constructor(tag = 'div') {
    this.tag = tag;
    this.children = [];
    this.attrs = {};
    this.style = {};
    this.listeners = {};
    this.textContent = '';
    this.value = '';
    this.className = '';
    this._innerHTML = '';
  }
  set innerHTML(value) {
    this._innerHTML = value;
    this.children = [];
  }
  get innerHTML() {
    return this._innerHTML;
  }
  append(...children) {
    this.children.push(...children);
  }
  appendChild(child) {
    this.children.push(child);
  }
  setAttribute(name, value) {
    this.attrs[name] = value;
  }
  addEventListener(name, callback) {
    this.listeners[name] = callback;
  }
  click() {
    assert.ok(this.listeners.click, 'no click listener on ' + this.tag);
    return this.listeners.click();
  }
  submit() {
    assert.ok(this.listeners.submit, 'no submit listener on ' + this.tag);
    return this.listeners.submit({ preventDefault() {} });
  }
}
const elements = new Map();
function get(id) {
  if (!elements.has(id)) elements.set(id, new Element(id));
  return elements.get(id);
}
const document = {
  getElementById: get,
  createElement: (tag) => new Element(tag),
};
const opened = [];
const timers = [];
const window = {
  open: (url, target, flags) => {
    opened.push({url, target, flags});
  },
  setTimeout: (fn) => {
    timers.push(fn);
    return timers.length;
  },
};
const copied = [];
const navigator = {
  clipboard: {
    writeText: (value) => {
      copied.push(value);
      return Promise.resolve();
    },
  },
};
vm.runInNewContext(bundled, {
  document, window, navigator, URLSearchParams,
});

// Default protected case correctly DENIES unapproved email, with no effect.
assert.equal(get('scenarios').children.length, 5, 'five synthetic tool choices');
assert.equal(get('with').attrs['aria-pressed'], 'true');
get('approval').value = 'none';
get('run').click();
let trace = JSON.parse(get('trace').textContent);
assert.equal(trace.tool_request.name, 'send_email');
assert.equal(trace.decision, 'denied');
assert.equal(trace.reason, 'approval_not_configured');
assert.equal(trace.handler_executed, false);
assert.equal(trace.real_world_side_effects, false);
assert.equal(get('outbox-count').textContent, '0');

// An explicit user approval runs the fictional email handler once.
get('approval').value = 'approve';
get('run').click();
trace = JSON.parse(get('trace').textContent);
assert.equal(trace.policy_enforced, true);
assert.equal(trace.decision, 'allowed');
assert.equal(trace.reason, 'approved');
assert.equal(trace.handler_executed, true);
assert.equal(trace.sandbox_result.delivered, false);
assert.equal(get('outbox-count').textContent, '1');
assert.equal(get('approval').value, 'none', 'approval must be single-use');

// A second call, without renewed approval, is denied and adds no email.
get('run').click();
trace = JSON.parse(get('trace').textContent);
assert.equal(trace.decision, 'denied');
assert.equal(get('outbox-count').textContent, '1');

// Explicit human refusal also denies.
get('approval').value = 'deny';
get('run').click();
trace = JSON.parse(get('trace').textContent);
assert.equal(trace.reason, 'approval_denied');
assert.equal(get('outbox-count').textContent, '1');

// Unguarded existing handler actually executes in the memory-only sandbox.
get('without').click();
get('run').click();
trace = JSON.parse(get('trace').textContent);
assert.equal(trace.policy_enforced, false);
assert.equal(trace.decision, 'outside_policy_boundary');
assert.equal(trace.handler_executed, true);
assert.equal(get('outbox-count').textContent, '2');

// Allowed read-only handler executes and returns a synthetic document.
get('with').click();
get('scenarios').children[0].click();
get('run').click();
trace = JSON.parse(get('trace').textContent);
assert.equal(trace.tool_request.name, 'read_document');
assert.equal(trace.decision, 'allowed');
assert.equal(trace.handler_executed, true);
assert.equal(get('read-count').textContent, '1');

// Deleted sample file remains intact behind guard; unguarded local handler
// can change only the in-memory fixture.
get('scenarios').children[2].click();
get('run').click();
trace = JSON.parse(get('trace').textContent);
assert.equal(trace.decision, 'denied');
assert.equal(get('file-status').textContent, 'Present');
get('without').click();
get('run').click();
trace = JSON.parse(get('trace').textContent);
assert.equal(trace.handler_executed, true);
assert.equal(get('file-status').textContent, 'Deleted (in memory)');

// No shell handler exists, even when the policy is bypassed.
get('scenarios').children[4].click();
get('run').click();
trace = JSON.parse(get('trace').textContent);
assert.equal(trace.handler_executed, false);
assert.equal(trace.reason, 'handler_not_registered');

// Reset changes only local fixture state, then guided walkthrough shows
// three distinct states with observable outbox counts.
get('reset-sandbox').click();
assert.equal(get('outbox-count').textContent, '0');
assert.equal(get('file-status').textContent, 'Present');
assert.equal(get('audit').textContent, '[]');
get('guided').click();
trace = JSON.parse(get('trace').textContent);
assert.equal(trace.tool_request.name, 'send_email');
assert.equal(trace.decision, 'outside_policy_boundary');
assert.equal(get('outbox-count').textContent, '1');
assert.equal(timers.length, 1);
timers.shift()();
trace = JSON.parse(get('trace').textContent);
assert.equal(trace.decision, 'denied');
assert.equal(get('outbox-count').textContent, '1');
assert.equal(timers.length, 1);
timers.shift()();
trace = JSON.parse(get('trace').textContent);
assert.equal(trace.reason, 'approved');
assert.equal(trace.handler_executed, true);
assert.equal(get('outbox-count').textContent, '2');
assert.equal(get('approval').value, 'none');
assert.equal(timers.length, 1);
timers.shift()();

// Feedback prepares a GitHub issue draft but cannot secretly submit data.
get('framework').value = 'Custom Python agent';
get('interest').value = 'Yes, this month';
get('problem').value = 'Need human approval before outbound email';
get('feedback-form').submit();
assert.equal(opened.length, 1);
const url = new URL(opened[0].url);
assert.equal(url.origin, 'https://github.com');
assert.equal(url.pathname, '/chirayukapoor5/agentshield/issues/new');
assert.ok(url.searchParams.get('body').includes('outbound email'));
assert.ok(get('feedback-status').textContent.includes('Submit'));
console.log('Sandbox verified: 5 scenarios, one-time approval/deny, real in-memory handlers, reset, 3-step walkthrough, GitHub feedback; no external side effects.');
