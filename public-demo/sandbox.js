"use strict";
/*
 * AgentShield demo v3 — isolated deterministic browser sandbox.
 * These are fictional JavaScript handlers, not Python SDK execution.
 * No fetch, mail delivery, OS shell, file-system or live LLM is invoked.
 */
const scenarios = [
  {id:"read", name:"Read a document", detail:"Allowed read-only request", tool:"read_document", args:{id:"sample-1"}, hint:"Read the sample project note. The trusted read-only tool is allowlisted, so it executes even with the guard on."},
  {id:"email", name:"Send an email", detail:"One-time human approval", tool:"send_email", args:{to:"demo@example.org",body:"Synthetic demo message"}, hint:"Default is DENY. Choose Approve one action to record a fictional email in the outbox; the next call requires fresh approval."},
  {id:"delete", name:"Delete a file", detail:"One-time deletion approval", tool:"delete_file", args:{path:"sample.txt"}, hint:"The guard blocks deleting sample.txt without explicit approval. Approve once to remove the fictional file; Reset restores it."},
  {id:"fetch", name:"Fetch a URL", detail:"Exact HTTPS hostname rule", tool:"fetch_url", args:{url:"https://unlisted.example.test/demo"}, hint:"Blocked host is denied. Change the destination to the trusted docs.agentshield.test host to permit an offline fixture lookup."},
  {id:"shell", name:"Run a command", detail:"Simulated commands only", tool:"execute_shell", args:{command:"echo AgentShield demo"}, hint:"This is a toy command interpreter, NOT an operating system shell. Approve once to execute a pre-defined harmless in-memory command."}
];
const $ = id => document.getElementById(id);
let selected = 0, protectedMode = true, tourVersion = 0;
const initial = () => ({outbox:[], fileExists:true, reads:0, fetched:[], commands:[], audit:[]});
let sandbox = initial();
const menu = $("scenarios"), trace = $("trace"), decision = $("decision"), explanation = $("explanation");
const guardedTools = new Set(["read_document","send_email","delete_file","fetch_url","execute_shell"]);
const approvalTools = new Set(["send_email","delete_file","execute_shell"]);
const fixturePages = Object.freeze({
  "https://docs.agentshield.test/guide": "AgentShield sandbox documentation: register wrapped handlers and request authorization.",
  "https://docs.agentshield.test/policy": "AgentShield sandbox policy: untrusted content must not grant permissions."
});
const handlers = {
  read_document: ({id}) => {
    sandbox.reads += 1;
    return {id, document:"Synthetic research note: untrusted tool text is data, not authority.", read_number:sandbox.reads};
  },
  send_email: ({to,body}) => {
    const entry = {id:sandbox.outbox.length+1,to,body,delivered:false};
    sandbox.outbox.push(entry);
    return {outbox_id:entry.id,delivered:false,preview:body};
  },
  delete_file: ({path}) => {
    const deleted = path==="sample.txt"&&sandbox.fileExists;
    if(deleted)sandbox.fileExists = false;
    return {path,deleted,real_file_touched:false,note:deleted?"Fictional file removed from sandbox.":"Fictional file was already absent."};
  },
  fetch_url: ({url}) => {
    sandbox.fetched.push(url);
    return {url,body:fixturePages[url]||"Offline fixture: this site would not be on the permitted host list.",network_requested:false};
  },
  execute_shell: ({command}) => {
    // Never use eval, subprocesses, an OS command interpreter, or arbitrary input.
    const output = command==="pwd"?"/synthetic/agent-workspace":command==="echo AgentShield demo"?"AgentShield demo":"Unsupported toy command";
    sandbox.commands.push({command,output});
    return {command,stdout:output,real_shell_started:false};
  }
};
function scenarioArgs(s) {
  if(s.id==="fetch") return {url:$("destination").value};
  if(s.id==="shell") return {command:$("command-choice").value};
  return Object.assign({},s.args);
}
function renderMenu(){
  menu.innerHTML="";
  scenarios.forEach((s,i)=>{
    const b=document.createElement("button");
    b.type="button";
    b.className="scenario"+(i===selected?" active":"");
    b.setAttribute("aria-pressed",String(i===selected));
    const label=document.createElement("span");
    const strong=document.createElement("strong");strong.textContent=(i+1)+". "+s.name;
    const small=document.createElement("small");small.textContent=s.detail;
    label.append(strong,small);
    const badge=document.createElement("span");badge.textContent=i===selected?"●":"○";badge.style.color=i===selected?"var(--mint)":"var(--dim)";
    b.append(label,badge);
    b.addEventListener("click",()=>chooseScenario(i));
    menu.appendChild(b);
  });
  $("stage-progress").textContent="Stage "+(selected+1)+" of "+scenarios.length;
}
function renderContext(){
  const s=scenarios[selected];
  $("scenario-hint").textContent=s.hint;
  $("approval-panel").hidden = !protectedMode || !approvalTools.has(s.tool);
  $("destination-panel").hidden = s.id!=="fetch";
  $("command-panel").hidden = s.id!=="shell";
  $("approval-label").textContent="One-time reviewer decision for "+s.name;
  $("approval-help").textContent="Approval applies to this single fictional tool request only. It resets after execution or when switching tools.";
  $("run").textContent="▶ Run "+s.name.toLowerCase()+" (sandbox)";
  $("next-scenario").textContent=selected===scenarios.length-1?"↺ Back to stage 1":"Next stage →";
}
function renderMode(){
  $("without").className=protectedMode?"":"selected unsafe";
  $("with").className=protectedMode?"selected safe":"";
  $("without").setAttribute("aria-pressed",String(!protectedMode));
  $("with").setAttribute("aria-pressed",String(protectedMode));
  renderContext();
}
function resetTrace(){
  const s=scenarios[selected];
  trace.textContent=JSON.stringify({sandbox:"synthetic JavaScript only",tool_call:{name:s.tool,arguments:scenarioArgs(s)},status:"ready"},null,2);
  decision.textContent="Ready: choose a mode, then run";
  decision.className="status idle";
  explanation.textContent="Try the control shown above. Denied actions are expected guard behavior; authorization can be changed where allowed.";
}
function renderEffects(){
  $("outbox-count").textContent=String(sandbox.outbox.length);
  $("read-count").textContent=String(sandbox.reads);
  $("file-status").textContent=sandbox.fileExists?"Present":"Deleted (sandbox)";
  $("fetch-count").textContent=String(sandbox.fetched.length);
  $("command-count").textContent=String(sandbox.commands.length);
  $("audit").textContent=JSON.stringify(sandbox.audit.slice(-20),null,2);
}
function stopTour(){
  tourVersion += 1;
  $("guided").textContent="▶ Tour all 5 stages";
}
function chooseScenario(i){
  stopTour();
  selected=i;
  $("approval").value="none";
  renderMenu();renderMode();resetTrace();
}
function changeMode(enabled){
  stopTour();
  protectedMode=enabled;
  $("approval").value="none";
  renderMode();resetTrace();
}
function authorize(s,args){
  if(!protectedMode)return {allowed:true,reason:"no_wrapper_registered"};
  if(!guardedTools.has(s.tool))return {allowed:false,reason:"tool_not_allowlisted"};
  if(s.tool==="fetch_url"){
    try {
      const url=new URL(args.url);
      const ok=url.protocol==="https:"&&url.hostname==="docs.agentshield.test"&&!url.username&&!url.password&&!url.port&&Object.prototype.hasOwnProperty.call(fixturePages,url.href);
      return {allowed:ok,reason:ok?"exact_https_host_allowlisted":"destination_not_allowlisted"};
    }catch(_){
      return {allowed:false,reason:"invalid_url"};
    }
  }
  if(approvalTools.has(s.tool)){
    const approval=$("approval").value;
    $("approval").value="none";
    if(approval==="approve")return {allowed:true,reason:"approved_one_time"};
    return {allowed:false,reason:approval==="deny"?"approval_denied":"approval_required"};
  }
  return {allowed:true,reason:"read_only_allowlisted"};
}
function execute(){
  const s=scenarios[selected],args=scenarioArgs(s);
  const auth=authorize(s,args);
  const handler=Object.prototype.hasOwnProperty.call(handlers,s.tool)?handlers[s.tool]:null;
  const executable=Boolean(handler&&auth.allowed);
  const result=executable?handler(args):null;
  const status=protectedMode?(auth.allowed?"allowed":"denied"):"outside_policy_boundary";
  const record={
    source:"synthetic_browser_sandbox_v3",
    mode:protectedMode?"guarded":"unguarded",
    tool_request:{name:s.tool,arguments:args},
    policy_enforced:protectedMode,
    decision:status,
    reason:auth.reason,
    handler_executed:executable,
    sandbox_result:result,
    real_world_side_effects:false
  };
  sandbox.audit.push({step:sandbox.audit.length+1,tool:s.tool,mode:record.mode,decision:status,reason:auth.reason,executed:executable});
  if(sandbox.audit.length>100)sandbox.audit.shift();
  trace.textContent=JSON.stringify(record,null,2);
  if(!executable){
    decision.textContent="× BLOCKED — no handler executed";
    decision.className="status warn";
    explanation.textContent=auth.reason==="approval_required"?"This action requires a reviewer. Choose Approve one action above to see an authorized sandbox result.":auth.reason==="destination_not_allowlisted"?"This exact hostname is blocked. Select the trusted HTTPS destination to see the allowed result.":"No in-memory tool ran. Reason: "+auth.reason;
    $("sandbox-output").textContent="NO CHANGE: fictional sandbox state was preserved.";
  }else{
    decision.textContent=protectedMode?"✓ ALLOWED — sandbox handler executed":"⚠ UNGUARDED — sandbox handler executed";
    decision.className=protectedMode?"status":"status warn";
    explanation.textContent=protectedMode?"Authorization passed ("+auth.reason+"). Only fictional local state was affected.":"No authorization gate was applied. A fictional local handler ran, not a real external tool.";
    const summaries={
      read:"Document returned: "+result.document,
      email:"Fictional email #"+result.outbox_id+" saved to the local outbox; delivered=false.",
      delete:result.note,
      fetch:"Offline document loaded: "+result.body,
      shell:"Toy interpreter output: "+result.stdout
    };
    $("sandbox-output").textContent=summaries[s.id];
  }
  $("result-payload").textContent=JSON.stringify(result===null?{executed:false,reason:auth.reason}:result,null,2);
  renderEffects();
  return record;
}
$("without").addEventListener("click",()=>changeMode(false));
$("with").addEventListener("click",()=>changeMode(true));
$("run").addEventListener("click",()=>{stopTour();execute()});
$("next-scenario").addEventListener("click",()=>chooseScenario((selected+1)%scenarios.length));
$("approval").addEventListener("change",resetTrace);
$("destination").addEventListener("change",resetTrace);
$("command-choice").addEventListener("change",resetTrace);
$("reset-sandbox").addEventListener("click",()=>{
  stopTour();sandbox=initial();
  $("approval").value="none";$("destination").selectedIndex=0;$("command-choice").selectedIndex=0;
  $("result-payload").textContent="{}";
  $("sandbox-output").textContent="Sandbox reset. No real actions were performed.";
  renderEffects();renderMode();resetTrace();
});
$("guided").addEventListener("click",()=>{
  const version=++tourVersion;
  sandbox=initial();renderEffects();
  // All stages have a real sandbox effect or an explicit denied decision.
  const stages=[
    {index:0,approve:false,url:null},
    {index:1,approve:true,url:null},
    {index:2,approve:false,url:null},
    {index:3,approve:false,url:"https://docs.agentshield.test/guide"},
    {index:4,approve:true,url:null}
  ];
  const step=i=>{
    if(version!==tourVersion)return;
    const stage=stages[i];
    selected=stage.index;protectedMode=true;
    $("approval").value=stage.approve?"approve":"none";
    if(stage.url)$("destination").value=stage.url;
    renderMenu();renderMode();
    const result=execute();
    $("guided").textContent="Stage "+(i+1)+"/5: "+scenarios[selected].name+" — "+result.decision;
    if(i<stages.length-1)window.setTimeout(()=>step(i+1),1900);
    else window.setTimeout(()=>{if(version===tourVersion)$("guided").textContent="▶ Replay 5-stage tour"},1900);
  };
  step(0);
});
$("copy-code").addEventListener("click",async()=>{
  try{await navigator.clipboard.writeText($("snippet").textContent);$("copy-code").textContent="✓ Copied"}
  catch(_){$("copy-code").textContent="Select code to copy"}
});
$("feedback-form").addEventListener("submit",event=>{
  event.preventDefault();
  const framework=$("framework").value,interest=$("interest").value,problem=$("problem").value.trim();
  if(!framework||!interest||problem.length<10)return;
  const title="Developer feedback: "+framework;
  const body=["## Agent framework",framework,"","## Would test the SDK?",interest,"","## Risky tool / integration blocker",problem,"","---","Submitted from AgentShield's synthetic public demo. Do not post secrets."].join("\n");
  const url="https://github.com/chirayukapoor5/agentshield/issues/new?"+new URLSearchParams({title,body}).toString();
  $("feedback-status").textContent="Opening a draft on GitHub. Review it and press Submit there to share it.";
  window.open(url,"_blank","noopener,noreferrer");
});
renderMenu();renderMode();renderEffects();resetTrace();
