/**
 * Dependency-free DOM-stub regression gate for all five public demo stages.
 * A separate headless Chromium E2E gate verifies actual browser behavior.
 */
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import vm from "node:vm";

const html=readFileSync("public-demo/index.html","utf8");
assert.ok(html.includes('data-demo-version="sandbox-all-five-v3"'));
assert.ok(html.includes('src="sandbox.js"'));
const source=readFileSync("public-demo/sandbox.js","utf8");
class Element {
  constructor(id="div"){
    this.id=id;this.children=[];this.attrs={};this.style={};this.listeners={};
    this.textContent="";this.value="";this.className="";this.hidden=false;
    this.selectedIndex=0;this._innerHTML="";
  }
  set innerHTML(v){this._innerHTML=v;this.children=[];}
  get innerHTML(){return this._innerHTML;}
  append(...children){this.children.push(...children);}
  appendChild(child){this.children.push(child);}
  setAttribute(k,v){this.attrs[k]=v;}
  addEventListener(k,fn){this.listeners[k]=fn;}
  click(){assert.ok(this.listeners.click,"Missing click: "+this.id);return this.listeners.click();}
  change(){assert.ok(this.listeners.change,"Missing change: "+this.id);return this.listeners.change();}
  submit(){assert.ok(this.listeners.submit,"Missing submit: "+this.id);return this.listeners.submit({preventDefault(){}});}
}
const nodes=new Map();
function get(id){if(!nodes.has(id))nodes.set(id,new Element(id));return nodes.get(id);}
get("approval").value="none";
get("destination").value="https://unlisted.example.test/demo";
get("command-choice").value="echo AgentShield demo";
const document={getElementById:get,createElement:(tag)=>new Element(tag)};
const timers=[],opened=[];
const window={
  setTimeout(fn){timers.push(fn);return timers.length;},
  open(url,target,flags){opened.push({url,target,flags});}
};
const navigator={clipboard:{writeText(){return Promise.resolve()}}};
vm.runInNewContext(source,{document,window,navigator,URL,URLSearchParams,Set,Object,JSON,String});
const result=()=>JSON.parse(get("trace").textContent);
const choose=i=>get("scenarios").children[i].click();
const run=()=>{get("run").click();return result();};
assert.equal(get("scenarios").children.length,5);

// 1. Read-only: guard allows; real in-memory handler returns a document.
assert.equal(run().decision,"allowed");
assert.equal(result().handler_executed,true);
assert.equal(get("read-count").textContent,"1");

// 2. Email: deny by default, explicit approve once, deny on next call.
choose(1);
assert.equal(run().reason,"approval_required");
assert.equal(get("outbox-count").textContent,"0");
get("approval").value="approve";
assert.equal(run().reason,"approved_one_time");
assert.equal(get("outbox-count").textContent,"1");
assert.equal(get("approval").value,"none");
assert.equal(result().sandbox_result.delivered,false);
assert.equal(run().reason,"approval_required");
assert.equal(get("outbox-count").textContent,"1");
get("without").click();
assert.equal(run().decision,"outside_policy_boundary");
assert.equal(get("outbox-count").textContent,"2");
get("with").click();

// 3. Delete: protect file, then authorize a single synthetic deletion.
choose(2);
assert.equal(get("approval-panel").hidden,false);
assert.equal(run().decision,"denied");
assert.equal(get("file-status").textContent,"Present");
get("approval").value="deny";
assert.equal(run().reason,"approval_denied");
get("approval").value="approve";
assert.equal(run().decision,"allowed");
assert.equal(get("file-status").textContent,"Deleted (sandbox)");
assert.equal(result().sandbox_result.real_file_touched,false);
assert.equal(run().decision,"denied");

// 4. URL: exact hostname fail closed; trusted host returns fixture body.
choose(3);
assert.equal(get("destination-panel").hidden,false);
assert.equal(get("approval-panel").hidden,true);
assert.equal(run().reason,"destination_not_allowlisted");
assert.equal(get("fetch-count").textContent,"0");
get("destination").value="https://docs.agentshield.test/guide";
get("destination").change();
assert.equal(run().decision,"allowed");
assert.equal(get("fetch-count").textContent,"1");
assert.equal(result().sandbox_result.network_requested,false);
assert.ok(result().sandbox_result.body.includes("documentation"));

// 5. Shell: toy interpreter only, and approval is consumed.
choose(4);
assert.equal(get("command-panel").hidden,false);
assert.equal(run().reason,"approval_required");
assert.equal(get("command-count").textContent,"0");
get("approval").value="approve";
assert.equal(run().reason,"approved_one_time");
assert.equal(get("command-count").textContent,"1");
assert.equal(result().sandbox_result.real_shell_started,false);
assert.equal(result().sandbox_result.stdout,"AgentShield demo");
get("command-choice").value="pwd";
get("command-choice").change();
get("approval").value="approve";
assert.equal(run().sandbox_result.stdout,"/synthetic/agent-workspace");

// Next-stage control wraps back to first.
get("next-scenario").click();
assert.equal(get("stage-progress").textContent,"Stage 1 of 5");

// Reset clears ALL effects and recorded decisions.
get("reset-sandbox").click();
for(const [id,v] of [
  ["outbox-count","0"],["read-count","0"],["fetch-count","0"],["command-count","0"],["file-status","Present"]
])assert.equal(get(id).textContent,v);
assert.equal(get("audit").textContent,"[]");

// The guided tour exercises ALL five, with feedback after each phase.
get("guided").click();
let current=result();
assert.equal(current.tool_request.name,"read_document");
assert.equal(current.decision,"allowed");
for(const expected of [
  ["send_email","allowed"],["delete_file","denied"],
  ["fetch_url","allowed"],["execute_shell","allowed"]
]){
  assert.ok(timers.length,"tour callback missing");
  timers.shift()();
  current=result();
  assert.equal(current.tool_request.name,expected[0]);
  assert.equal(current.decision,expected[1]);
}
assert.equal(get("outbox-count").textContent,"1");
assert.equal(get("file-status").textContent,"Present");
assert.equal(get("fetch-count").textContent,"1");
assert.equal(get("command-count").textContent,"1");
assert.equal(JSON.parse(get("audit").textContent).length,5);
assert.ok(timers.length);
timers.shift()();

// Feedback form only creates a draft URL for GitHub.
get("framework").value="Custom Python agent";
get("interest").value="Yes, this month";
get("problem").value="I need explicit approval before tools delete files.";
get("feedback-form").submit();
assert.equal(opened.length,1);
const url=new URL(opened[0].url);
assert.equal(url.origin,"https://github.com");
assert.equal(url.pathname,"/chirayukapoor5/agentshield/issues/new");
assert.ok(url.searchParams.get("body").includes("delete files"));
console.log("PASS: all 5 functional stages, unguarded/guarded, one-use approvals, host policy, offline command, full guided tour, state reset and issue draft.");
