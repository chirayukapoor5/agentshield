/**
 * Dependency-free runtime smoke test of the public demo script.
 * Mock DOM; assertions verify UI state, never real tool execution or LLM ASR.
 * Run: node scripts/test_public_demo.mjs
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync('public-demo/index.html', 'utf8');
const matches = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)];
assert.equal(matches.length, 1, 'expected a single local interactive script');

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
vm.runInNewContext(matches[0][1], {
  document, window, navigator, URLSearchParams,
});

assert.equal(get('scenarios').children.length, 5, 'five demonstration choices');
assert.equal(get('with').attrs['aria-pressed'], 'true');
get('run').click();
let trace = JSON.parse(get('trace').textContent);
assert.equal(trace.tool_request.name, 'send_email');
assert.equal(trace.policy_enforced, true);
assert.equal(trace.decision, 'denied');
assert.equal(trace.reason, 'approval_not_configured');
assert.equal(trace.handler_executed, false, 'no actual tool may execute');

get('without').click();
assert.equal(get('without').attrs['aria-pressed'], 'true');
get('run').click();
trace = JSON.parse(get('trace').textContent);
assert.equal(trace.policy_enforced, false);
assert.equal(trace.decision, 'outside_policy_boundary');
assert.equal(trace.handler_executed, false);

get('with').click();
get('scenarios').children[0].click();
get('run').click();
trace = JSON.parse(get('trace').textContent);
assert.equal(trace.tool_request.name, 'read_document');
assert.equal(trace.decision, 'allowed');
assert.equal(trace.handler_executed, false);

// Check the developer-feedback form builds a real GitHub issue draft URL.
// The site must never directly submit the user's input to a hidden endpoint.
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
console.log('Public showcase interactions verified: 5 scenarios, both guard modes, read/deny, issue draft; 0 tool executions.');
