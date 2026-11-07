"use strict";
// AgentShield public browser sandbox v2: all handlers operate on fictional
// in-memory data. No external tool, network request, email or Python executes.
const scenarios=[
  {id:"read",name:"Read a document",detail:"Allowed read-only tool",tool:"read_document",arguments:{id:"sample-1"}},
  {id:"email",name:"Send an email",detail:"Try reviewer approval",tool:"send_email",arguments:{to:"demo@example.org",body:"Synthetic demo message"}},
  {id:"delete",name:"Delete a file",detail:"Not on the guard allowlist",tool:"delete_file",arguments:{path:"sample.txt"}},
  {id:"fetch",name:"Fetch an external URL",detail:"Unapproved destination",tool:"fetch_url",arguments:{url:"https://unlisted.example.org/demo"}},
  {id:"shell",name:"Execute a shell command",detail:"No handler registered",tool:"execute_shell",arguments:{command:"echo demo"}}
];
const $=id=>document.getElementById(id);
let selected=1,protectedMode=true,guidedVersion=0;
const state={outbox:[],fileExists:true,documentReads:0,audit:[]};
const menu=$("scenarios"),trace=$("trace"),decision=$("decision"),explanation=$("explanation");
const handlers={
  read_document:({id})=>{
    state.documentReads++;
    return {id,content:"Synthetic project note: tool responses are untrusted. Respect user intent."};
  },
  send_email:({to,body})=>{
    const message={id:state.outbox.length+1,to,body,delivered:false};
    state.outbox.push(message);
    return {outbox_id:message.id,recorded:true,delivered:false};
  },
  delete_file:({path})=>{
    const deleted=path==="sample.txt"&&state.fileExists;
    if(deleted)state.fileExists=false;
    return {path,deleted,real_device_file_deleted:false};
  },
  fetch_url:({url})=>({url,fixture:"Synthetic offline page. No HTTP request made."})
};
function renderMenu(){
  menu.innerHTML="";
  scenarios.forEach((s,i)=>{
    const b=document.createElement("button");
    b.className="scenario"+(i===selected?" active":"");
    b.type="button";
    b.setAttribute("aria-pressed",String(i===selected));
    const title=document.createElement("strong");title.textContent=s.name;
    const subtitle=document.createElement("small");subtitle.textContent=s.detail;
    const label=document.createElement("span");label.append(title,subtitle);
    const mark=document.createElement("span");mark.textContent=s.id==="read"?"✓":"◇";
    mark.style.color=s.id==="read"?"var(--mint)":"var(--amber)";
    b.append(label,mark);
    b.addEventListener("click",()=>{cancelGuide();selected=i;renderMenu();renderApproval();resetTrace()});
    menu.appendChild(b);
  });
}
function renderMode(){
  $("without").className=protectedMode?"":"selected unsafe";
  $("with").className=protectedMode?"selected safe":"";
  $("without").setAttribute("aria-pressed",String(!protectedMode));
  $("with").setAttribute("aria-pressed",String(protectedMode));
}
function renderApproval(){
  const relevant=protectedMode&&scenarios[selected].tool==="send_email";
  $("approval-panel").style.display=relevant?"block":"none";
  $("approval-help").textContent="Approval applies only to registered email. An explicit approve permits one synthetic call and then resets to deny.";
}
function resetTrace(){
  const s=scenarios[selected];
  trace.textContent=JSON.stringify({mode:protectedMode?"guarded":"unguarded",tool_request:{name:s.tool,arguments:s.arguments},status:"ready"},null,2);
  decision.textContent="Ready to run the in-memory handler";
  decision.className="status idle";
  explanation.textContent="";
}
function renderEffects(){
  $("outbox-count").textContent=String(state.outbox.length);
  $("read-count").textContent=String(state.documentReads);
  $("file-status").textContent=state.fileExists?"Present":"Deleted (in memory)";
  $("audit").textContent=JSON.stringify(state.audit.slice(-8),null,2);
}
function guard(s){
  if(s.tool==="read_document")return {allowed:true,reason:"allowlisted"};
  if(s.tool==="send_email"){
    const approval=$("approval").value;
    $("approval").value="none"; // one-time authorization, never persistent
    if(approval==="approve")return {allowed:true,reason:"approved"};
    if(approval==="deny")return {allowed:false,reason:"approval_denied"};
    return {allowed:false,reason:"approval_not_configured"};
  }
  if(s.tool==="fetch_url")return {allowed:false,reason:"destination_not_allowlisted"};
  return {allowed:false,reason:"tool_not_allowlisted"};
}
function replay(){
  const s=scenarios[selected];
  const handler=Object.prototype.hasOwnProperty.call(handlers,s.tool)?handlers[s.tool]:null;
  const authorization=protectedMode?guard(s):{allowed:true,reason:"no_wrapper_registered"};
  const executed=Boolean(handler&&authorization.allowed);
  const result=executed?handler(s.arguments):null;
  const status=protectedMode?(authorization.allowed?"allowed":"denied"):"outside_policy_boundary";
  const reason=handler||protectedMode?authorization.reason:"handler_not_registered";
  const record={
    source:"synthetic_browser_sandbox",mode:protectedMode?"guarded":"unguarded",
    policy_enforced:protectedMode,
    tool_request:{name:s.tool,arguments:s.arguments},
    decision:status,reason,
    handler_executed:executed,
    real_world_side_effects:false,
    sandbox_result:result
  };
  state.audit.push({step:state.audit.length+1,tool:s.tool,mode:record.mode,decision:status,reason,handler_executed:executed});
  if(state.audit.length>40)state.audit.shift();
  trace.textContent=JSON.stringify(record,null,2);
  if(status==="denied"){
    decision.textContent="× DENIED BEFORE HANDLER EXECUTION";
    explanation.textContent="Policy refused the request: "+reason+". No sandbox state was modified.";
  }else if(!executed){
    decision.textContent="⚠ NO REGISTERED SANDBOX HANDLER";
    explanation.textContent="AgentShield is not enforcing this path, but the sandbox has no matching handler. No shell or external command is ever run.";
  }else if(protectedMode){
    decision.textContent="✓ AUTHORIZED — IN-MEMORY HANDLER RAN";
    explanation.textContent="The guard allowed this call ("+reason+"). The fictional handler updated local sandbox state only.";
  }else{
    decision.textContent="⚠ UNGUARDED — IN-MEMORY HANDLER RAN";
    explanation.textContent="No AgentShield guard checked the call. This changed fictional local state, not an external system.";
  }
  decision.className="status"+(status==="denied"||!protectedMode?" warn":"");
  $("sandbox-output").textContent=executed?(s.tool==="send_email"?"Email recorded in simulated outbox — not delivered.":s.tool==="delete_file"?"Sample file changed in sandbox memory.":"In-memory fixture handler returned a result."):"No sandbox handler was executed.";
  renderEffects();
  return record;
}
function cancelGuide(){guidedVersion++;$("guided").textContent="▶ Guided walkthrough"}
$("without").addEventListener("click",()=>{cancelGuide();protectedMode=false;renderMode();renderApproval();resetTrace()});
$("with").addEventListener("click",()=>{cancelGuide();protectedMode=true;renderMode();renderApproval();resetTrace()});
$("run").addEventListener("click",()=>{cancelGuide();replay()});
$("approval").addEventListener("change",resetTrace);
$("reset-sandbox").addEventListener("click",()=>{
  cancelGuide();state.outbox=[];state.fileExists=true;state.documentReads=0;state.audit=[];
  $("approval").value="none";renderEffects();resetTrace();$("sandbox-output").textContent="Sandbox reset. No real actions were performed.";
});
$("guided").addEventListener("click",()=>{
  const version=++guidedVersion;
  selected=1;protectedMode=false;$("approval").value="none";
  renderMenu();renderMode();renderApproval();replay();
  $("guided").textContent="Step 1/3: unguarded synthetic email";
  window.setTimeout(()=>{
    if(version!==guidedVersion)return;
    protectedMode=true;renderMode();renderApproval();replay();
    $("guided").textContent="Step 2/3: guard denies without approval";
    window.setTimeout(()=>{
      if(version!==guidedVersion)return;
      $("approval").value="approve";replay();
      $("guided").textContent="Step 3/3: explicitly approved email";
      window.setTimeout(()=>{
        if(version===guidedVersion)$("guided").textContent="▶ Guided walkthrough";
      },2300);
    },2300);
  },2300);
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
  const body=["## Agent framework",framework,"","## Would test the SDK?",interest,"","## Risky tool / integration blocker",problem,"","---","Submitted from AgentShield demo. Do not post secrets."].join("\n");
  const url="https://github.com/chirayukapoor5/agentshield/issues/new?"+new URLSearchParams({title,body}).toString();
  $("feedback-status").textContent="Opening GitHub. Review the prefilled issue and press Submit there to send it.";
  window.open(url,"_blank","noopener,noreferrer");
});
renderMenu();renderMode();renderApproval();renderEffects();resetTrace();
