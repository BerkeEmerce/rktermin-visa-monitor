"use strict";
const REPO="BerkeEmerce/rktermin-visa-monitor";
const RAW="https://raw.githubusercontent.com/"+REPO+"/monitor-state/";
const API="https://api.github.com/repos/"+REPO+"/actions/runs?per_page=50";
const el=id=>document.getElementById(id);
const records=new Map(),loadedDays=new Set();
let archiveDays=[],lastApiFetch=0,apiRows=[],indexInfo={},busy=false,limit=30;
const dateFormat=new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/Berlin",day:"numeric",month:"short",year:"numeric"});
const timeFormat=new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/Berlin",hour:"2-digit",minute:"2-digit",hour12:false});
function node(tag,className,text){const e=document.createElement(tag);if(className)e.className=className;if(text!==undefined)e.textContent=text;return e;}
function validDate(value){const d=new Date(value);return Number.isFinite(d.getTime())?d:null;}
function stamp(value){const d=validDate(value);return d?dateFormat.format(d)+" · "+timeFormat.format(d):"Time unavailable";}
function monthName(value){if(!/^\d{4}-\d{2}$/.test(value))return "Unknown month";return new Intl.DateTimeFormat("en-GB",{month:"short",year:"numeric",timeZone:"UTC"}).format(new Date(value+"-01T12:00:00Z"));}
function expectedMonths(value){const d=validDate(value);if(!d)return [];const parts=new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Nicosia",year:"numeric",month:"2-digit"}).formatToParts(d);const year=Number(parts.find(p=>p.type==="year").value),month=Number(parts.find(p=>p.type==="month").value);return [0,1,2].map(i=>{const n=year*12+month-1+i;return {month:String(Math.floor(n/12))+"-"+String(n%12+1).padStart(2,"0"),checked:false,available:null,dates:[]};});}
function resultLabel(row){if(row.status==="AVAILABLE")return "Available";if(row.status==="UNAVAILABLE")return "No appointments";if(row.status==="SKIPPED")return "Skipped";if(row.status==="IN_PROGRESS")return "Running";if(row.status==="NOT_RECORDED")return "No saved result";return "Check failed";}
function safeRunUrl(row){return /^\d+$/.test(String(row.run_id))?"https://github.com/"+REPO+"/actions/runs/"+row.run_id:null;}
function renderRow(row){
 const box=node("details","run"),summary=node("summary");
 const time=node("div","time");time.append(node("span","",stamp(row.started_at)));
 time.append(node("small","",(row.source==="automatic"?"Automatic":"Manual")+(row.mode==="diagnostic"?" · diagnostic":"")+(row.attempt>1?" · attempt "+row.attempt:"")));
 summary.append(time);
 const months=node("div","months");
 const rows=Array.isArray(row.months)&&row.months.length?row.months:expectedMonths(row.started_at);
 rows.forEach(m=>{const checked=m.checked===true,yes=checked&&m.available===true;
 const chip=node("div","month"+(yes?" yes":!checked?" unknown":""));chip.append(node("b","",monthName(m.month)),node("span","",!checked?"Not checked":yes?"Yes · available":"No appointments"));months.append(chip);});
 summary.append(months,node("span","outcome"+(row.status==="AVAILABLE"?" available":!["UNAVAILABLE","SKIPPED","IN_PROGRESS"].includes(row.status)?" error":""),resultLabel(row)));
 box.append(summary);
 const detail=node("div","detail"),dl=node("dl");
 const add=(label,value)=>{dl.append(node("dt","",label),node("dd","",value));};
 if(row.reason)add("Detail",row.reason);
 if(row.error)add("Error",row.error);
 add("Started",stamp(row.started_at));
 if(row.checked_at)add("Check time",stamp(row.checked_at));
 if(row.finished_at)add("Finished",stamp(row.finished_at));
 const dates=rows.flatMap(m=>Array.isArray(m.dates)?m.dates:[]);if(dates.length)add("Available dates",dates.join(", "));
 if(row.captcha&&row.captcha.engine)add("CAPTCHA",row.captcha.engine+" · "+(row.captcha.accepted||0)+" accepted / "+(row.captcha.submitted||0)+" submitted");
 if(row.notification_error)add("Delivery","An appointment alert could not be confirmed.");
 if(row.delivery_errors)Object.entries(row.delivery_errors).forEach(([k,v])=>add(k==="email"?"Email":"Telegram",String(v)));
 add("Screenshots","Not captured for this run.");
 const url=safeRunUrl(row);if(url){dl.append(node("dt","","Run log"));const dd=node("dd"),a=node("a","","Open GitHub log ↗");a.href=url;a.target="_blank";a.rel="noopener";dd.append(a);dl.append(dd);}
 detail.append(dl);box.append(detail);return box;
}
function allRows(){const map=new Map(apiRows.map(r=>[r.id,r]));records.forEach((r,key)=>map.set(key,r));return [...map.values()].sort((a,b)=>(b.started_at||"").localeCompare(a.started_at||"")||(b.attempt||1)-(a.attempt||1));}
function render(){
 const all=allRows(),source=el("source").value,filtered=all.filter(r=>source==="all"||r.source===source);
 const host=el("runs");host.replaceChildren();
 if(!filtered.length)host.append(node("div","empty",source==="automatic"?"No automatic runs recorded yet.":"No run history yet. The next monitor run will appear here."));
 else filtered.slice(0,limit).forEach(row=>host.append(renderRow(row)));
 el("count").textContent=filtered.length+" recorded";
 const moreDays=archiveDays.some(day=>!loadedDays.has(day));
 el("more").hidden=filtered.length<=limit&&!moreDays;
 const checked=all.find(r=>Array.isArray(r.months)&&r.months.some(m=>m.checked===true));
 el("last-check").textContent=checked?stamp(checked.checked_at||checked.started_at):"No saved calendar check";
 el("last-result").textContent=checked?resultLabel(checked):"A successful workflow alone does not confirm a calendar check.";
 const auto=all.find(r=>r.source==="automatic"),age=auto&&validDate(auto.started_at)?Date.now()-new Date(auto.started_at).getTime():Infinity;
 el("health").textContent=!auto?"Awaiting automatic run":age>2*3600000?"Automatic checks overdue":auto.status==="IN_PROGRESS"?"Checking now":["UNAVAILABLE","AVAILABLE"].includes(auto.status)?"Running hourly":"Needs attention";
 el("health-detail").textContent=auto?"Last automatic run: "+stamp(auto.started_at):"Scheduled hourly · no automatic check confirmed yet";
 el("email").textContent=indexInfo.email_configured?"Email: configured for appointment alerts":"Email: setup needed";
}
async function getJson(url,missing=false){
 const response=await fetch(url,{cache:"no-store",credentials:"omit",headers:{Accept:"application/json"}});
 if(response.status===404&&missing)return null;
 if(!response.ok)throw new Error(response.status===403||response.status===429?"GitHub is temporarily limiting requests.":"Run history could not be loaded.");
 return response.json();
}
async function loadDay(day){if(!/^\d{4}-\d{2}-\d{2}$/.test(day))return;const data=await getJson(RAW+"run-history/"+day+".json");
 if(data.version!==1||!Array.isArray(data.runs))throw new Error("The run history format could not be read.");
 data.runs.forEach(r=>{if(r&&typeof r.id==="string"&&typeof r.started_at==="string")records.set(r.id,r);});loadedDays.add(day);}
async function loadApi(){
 if(Date.now()-lastApiFetch<300000)return;
 const data=await getJson(API);lastApiFetch=Date.now();
 apiRows=(data.workflow_runs||[]).filter(r=>r.name==="Visa appointment monitor").map(r=>({
 id:String(r.id)+":"+String(r.run_attempt||1),run_id:String(r.id),attempt:r.run_attempt||1,
 source:r.event==="schedule"?"automatic":"manual",started_at:r.run_started_at||r.created_at,
 status:r.status!=="completed"?"IN_PROGRESS":r.conclusion==="skipped"?"SKIPPED":r.conclusion==="success"?"NOT_RECORDED":"RUN_FAILED",
 months:[],reason:r.conclusion==="success"?"This older run has no archived per-month result. Open its GitHub log for details.":r.conclusion==="skipped"?"The workflow was skipped; no calendar months were checked.":"See the GitHub log for this workflow attempt."}));
}
async function refresh(force=false){
 if(busy)return;busy=true;el("refresh").disabled=true;const errors=[];
 try{
  const data=await getJson(RAW+"run-history/index.json",true);
  if(data){if(data.version!==1||!Array.isArray(data.days))throw new Error("The archive index could not be read.");indexInfo=data;archiveDays=data.days;await Promise.all(archiveDays.slice(0,2).map(loadDay));}
 }catch(error){errors.push(error.message);}
 try{await loadApi();}catch(error){errors.push(error.message);}
 el("notice").hidden=errors.length===0;
 if(errors.length)el("notice").textContent=errors.join(" ")+" Previously loaded results remain visible; missing results are never treated as no appointments.";
 render();busy=false;el("refresh").disabled=false;
}
el("refresh").addEventListener("click",()=>refresh(true));
el("source").addEventListener("change",()=>{limit=30;render();});
el("more").addEventListener("click",async()=>{el("more").disabled=true;try{const next=archiveDays.find(day=>!loadedDays.has(day));if(next)await loadDay(next);limit+=30;render();}catch(error){el("notice").hidden=false;el("notice").textContent=error.message;}finally{el("more").disabled=false;}});
document.addEventListener("visibilitychange",()=>{if(!document.hidden)refresh();});
setInterval(()=>{if(!document.hidden)refresh();},60000);
refresh();
