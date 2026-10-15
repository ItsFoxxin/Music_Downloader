"use strict";
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const size = n => { if (n == null) return "—"; const units=["B","KB","MB","GB","TB"]; let i=0; while(n>=1024&&i<4){n/=1024;i++;} return `${n.toFixed(i ? 1 : 0)} ${units[i]}`; };
const time = n => new Date(n * 1000).toLocaleString();
const empty = (title, text, icon="◇") => `<div class="empty"><span class="empty-icon">${icon}</span><strong>${esc(title)}</strong>${esc(text)}</div>`;
const badge = (label, tone="") => `<span class="badge ${tone}">${esc(label)}</span>`;
const requestedView=new URLSearchParams(location.search).get("view");
const initialView=new Set(["overview","requests","downloads","staging","library","history","settings"]).has(requestedView)?requestedView:"overview";
let state={status:null,torrents:[],torrentError:"",staging:[],jobs:[],library:[],requests:[]}, tab=initialView, activeReview=null, busy=false, token="", authenticated=false;

async function api(path, body){
  const response=await fetch(`./api/${path}`,{method:body===undefined?"GET":"POST",headers:{...(token?{"Authorization":`Bearer ${token}`}:{ }),"Content-Type":"application/json","X-Foxden-Request":"1"},body:body===undefined?undefined:JSON.stringify(body)});
  let data; try { data=await response.json(); } catch { throw new Error("The server returned an unreadable response."); }
  if(!response.ok){if(response.status===401) lock(); throw new Error(typeof data.detail==="string"?data.detail:JSON.stringify(data.detail||data));}
  return data;
}
function toast(message){$("toast").textContent=message;$("toast").hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$("toast").hidden=true,9000);}
function lock(){token="";authenticated=false;$("shell").hidden=true;$("login").hidden=false;$("token").value="";}
async function unlock(){
  try {if(token){await api("session",{});token="";$("token").value="";}state.status=await api("status");authenticated=true;$("login").hidden=true;$("shell").hidden=false;$("login-error").textContent="";await refresh();}
  catch(error){$("login-error").textContent=error.message;}
}
$("login-form").addEventListener("submit",e=>{e.preventDefault();token=$("token").value.trim();unlock();});
$("lock").addEventListener("click",async()=>{try{await api("logout",{});}catch{}lock();});
$("refresh").addEventListener("click",refresh);
$("search").addEventListener("input",render);
document.querySelectorAll("[data-tab]").forEach(b=>b.addEventListener("click",()=>{tab=b.dataset.tab;$("search").value="";render();}));

function ready(){
  const used=new Set(state.jobs.filter(j=>j.kind==="import"&&["queued","running","succeeded"].includes(j.status)).map(j=>j.payload.validation_id));
  return state.jobs.filter(j=>j.kind==="validate"&&j.status==="succeeded"&&!used.has(j.id));
}
function label(job){
  if(job.payload.source) return job.payload.source;
  if(job.payload.name) return `${job.payload.category}/${job.payload.name}`;
  if(job.result?.destination) return job.result.destination;
  const torrent=state.torrents.find(t=>t.hash===job.payload.torrent_hash);
  return torrent?.name || job.payload.torrent_hash || job.payload.import_id || "Magnet submission";
}
async function refresh(){
  if(!authenticated||busy)return;busy=true;
  try {
    const [status,jobs,staging,library,requests,torrents]=await Promise.allSettled([api("status"),api("jobs"),api("staging"),api("library"),api("requests"),api("torrents")]);
    for(const [key,result] of Object.entries({status,jobs,staging,library,requests})){
      if(result.status==="fulfilled")state[key]=result.value;else throw result.reason;
    }
    if(torrents.status==="fulfilled"){state.torrents=torrents.value;state.torrentError="";}else{state.torrents=[];state.torrentError=torrents.reason.message;}
    render();$("last-sync").textContent=`Updated ${new Date().toLocaleTimeString()}`;
  }catch(error){toast(error.message);}finally{busy=false;}
}
function table(head,rows){return `<div class="table-scroll"><table><thead><tr>${head.map(h=>`<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;}
function filter(items,fn){const term=$("search").value.toLowerCase();return items.filter(x=>fn(x).toLowerCase().includes(term));}
function torrentTable(){
  if(state.torrentError)return empty("Downloader is offline",state.torrentError,"↓");
  const rows=filter(state.torrents,t=>t.name);
  if(!rows.length)return empty("A quiet download queue","Add a magnet or open qBittorrent to start a download.","↓");
  return table(["Torrent","Progress","Transfer","State","Actions"],rows.map(t=>`<tr><td class="name"><span class="row-title">${esc(t.name)}</span><small>${size(t.size)} · ${esc(t.category||"Uncategorized")}</small></td><td>${Math.round(t.progress*100)}%<br><progress class="progress" max="1" value="${Number(t.progress)||0}" aria-label="Download progress"></progress></td><td><small>↓ ${size(t.dlspeed)}/s</small><small>↑ ${size(t.upspeed)}/s</small></td><td>${badge(t.state,t.progress<1?"warn":"")}</td><td><div class="actions"><button class="mini" data-action="validate-torrent" data-id="${esc(t.hash)}" ${t.progress<1?"disabled":""}>Validate</button><button class="mini" data-action="recheck" data-id="${esc(t.hash)}">Recheck</button><button class="mini" data-action="${/paused|stopped/.test(t.state)?"start":"stop"}" data-id="${esc(t.hash)}">${/paused|stopped/.test(t.state)?"Start":"Stop"}</button></div></td></tr>`));
}
function stagingTable(){
  const rows=filter(state.staging,f=>f.name);
  if(!rows.length)return empty("Staging is clear","Completed downloads will appear here when your staging folder is connected.","▱");
  return `<div class="expanded">For torrent completeness checks, validate from Downloads. Staging validation checks file stability and media readability without linking to a torrent.</div>`+table(["File or folder","Kind","Size","Action"],rows.map(f=>`<tr><td class="name">${esc(f.name)}</td><td>${badge(f.blocked?"Blocked link":f.directory?"Folder":"File",f.blocked?"error":"")}</td><td>${size(f.size)}</td><td><button class="mini" data-action="validate-source" data-id="${esc(f.path)}" ${f.blocked?"disabled":""}>Validate files →</button></td></tr>`));
}
function requestTable(){
  const rows=filter(state.requests,r=>`${r.title} ${r.media_type} ${r.status} ${r.query}`);
  if(!rows.length)return empty("Your request list is ready","Request a movie or TV show by name, metadata link, or magnet.","＋");
  const choices=state.torrents.map(t=>`<option value="${esc(t.hash)}">${esc(t.name)}</option>`).join("");
  return `<div class="expanded">Magnet requests are tracked automatically. For a name or IMDb/TMDB link, add the matching download in qBittorrent and attach it here.</div>`+table(["Request","Type","State","Next step"],rows.map(r=>{
    const tone=r.status==="failed"?"error":["waiting_for_user","needs_review"].includes(r.status)?"warn":"";
    let action="";
    if(["waiting_for_user","failed"].includes(r.status)) action=`<div class="actions"><a class="mini button" href="./request-browser/${r.id}">Guided browser ↗</a>${choices?`<select id="torrent-${r.id}" aria-label="Torrent for ${esc(r.title)}"><option value="">Choose a torrent…</option>${choices}</select><button class="mini" data-action="attach-request" data-id="${r.id}">Attach</button>`:`<small>Open qBittorrent and add a matching download.</small>`}</div>`;
    else if(r.status==="needs_review") action=`<button class="mini" data-action="review" data-id="${esc(r.validation_id)}">Review import →</button>`;
    else action=`<small>${r.error?esc(r.error):r.status==="complete"?"Imported and verified.":"Fox Den is following this request."}</small>`;
    return `<tr><td class="name"><span class="row-title">${esc(r.title)}</span><small>${esc(r.query)}</small></td><td>${esc(r.media_type)}</td><td>${badge(r.status.replaceAll("_"," "),tone)}</td><td>${action}</td></tr>`;
  }));
}
function libraryTable(){
  const rows=filter(state.library,f=>f.destination);
  if(!rows.length)return empty("Make room for movie night","Your approved imports will appear here with their checksums and last verification.","▤");
  return table(["Library folder","Files","Health","Last checked","Action"],rows.map(f=>`<tr><td class="name">${esc(f.destination)}<small>Imported ${time(f.created)}</small></td><td>${f.manifest.files.length}</td><td>${badge(f.health,f.health==="verified"?"":"error")}</td><td><small>${f.checked?time(f.checked):"Not checked"}</small></td><td><button class="mini" data-action="audit" data-id="${f.id}">Verify library</button></td></tr>`));
}
function historyTable(){
  const rows=filter(state.jobs,j=>`${label(j)} ${j.kind} ${j.status}`);
  if(!rows.length)return empty("The story starts here","Validation, imports, torrent actions, and library checks are recorded here.","◷");
  return table(["Activity","Created","Status","Details"],rows.map(j=>`<tr><td class="name">${esc(label(j))}<small>${esc(j.kind.replaceAll("_"," "))}</small></td><td><small>${time(j.created)}</small></td><td>${badge(j.result?.issues?.length?"issues found":j.status,j.status==="failed"||j.result?.issues?.length?"error":["queued","running","interrupted"].includes(j.status)?"warn":"")}</td><td>${j.error?`<span class="job-error">${esc(j.error)}</span>`:j.kind==="validate"&&j.status==="succeeded"?`<button class="mini" data-action="review" data-id="${j.id}">View report</button>`:j.result?.issues?.length?`<span class="job-error">${j.result.issues.map(x=>`${esc(x.path)}: ${esc(x.issue)}`).join("<br>")}</span>`:esc(j.result?.message||j.result?.destination|| (j.result?.checked_files?`${j.result.checked_files} checksums checked`:j.status==="running"?"Working through the files…":""))}</td></tr>`));
}
function settingsPanel(){
  const s=state.status;
  const fields=[["qBittorrent connection",s.qbit_configured?"Configured in .env":"Add QBIT_URL to .env"],["qBittorrent download root",s.qbit_download_root],["Staging mount (read only)",s.staging],["Media mount",s.media],["File validation",s.full_decode?"Metadata + full audio/video decode + SHA-256":"Metadata + SHA-256; full decode disabled"],["Media tools",`ffprobe: ${s.ffprobe_available?"available":"missing"} · ffmpeg: ${s.ffmpeg_available?"available":"missing"}`],["Import behavior","Reviewed copies · source preserved · no overwrite"],["Library scope","Tracks files imported through Fox Den. Music has its own library view."]];
  return `<div class="settings">${fields.map(([k,v])=>`<dl><dt>${esc(k)}</dt><dd>${esc(v)}</dd></dl>`).join("")}</div><div class="expanded">Edit your private .env on the server and recreate the Docker services to update connections. Credentials are never sent to this browser.</div>`;
}
function render(){
  if(!state.status)return;
  $("app-version").textContent=`Fox Den Media · v${state.status.version}`;
  const names={overview:["Overview","From download <br>to movie night<span>.</span>","On the way in"],requests:["Requests","Ask once. Follow every step<span>.</span>","Movie & TV requests"],downloads:["Downloads","A little closer to play<span>.</span>","Download queue"],staging:["Staging & review","Almost home<span>.</span>","Your staging folder"],library:["Movie & TV library","A collection worth keeping<span>.</span>","Imported movies & TV"],history:["Activity","Every step, accounted for<span>.</span>","Workspace activity"],settings:["Connections","Everything, connected<span>.</span>","Your workspace settings"]};
  $("breadcrumb").textContent=names[tab][0];$("page-title").innerHTML=names[tab][1];$("panel-title").textContent=names[tab][2];
  $("panel-eyebrow").textContent=tab==="settings"?"CONFIGURED ON YOUR SERVER":tab==="history"?"DURABLE JOB HISTORY":tab==="requests"?"REQUEST TO VERIFIED LIBRARY":tab==="staging"?"WAITING OUTSIDE THE LIBRARY":tab==="library"?"A VERIFIED PLACE TO LAND":"LIVE FROM YOUR DOWNLOADER";
  document.querySelectorAll("[data-tab]").forEach(b=>{b.classList.toggle("active",b.dataset.tab===tab);if(b.dataset.tab===tab)b.setAttribute("aria-current","page");else b.removeAttribute("aria-current");});
  $("overview-extra").hidden=tab!=="overview";$("review-panel").hidden=!["overview","staging"].includes(tab);$("search").hidden=tab==="settings";
  $("connection").textContent=state.torrentError?"qBittorrent offline":"qBittorrent connected";$("connection").className=`badge ${state.torrentError?"warn":""}`;
  $("demo-banner").hidden=!state.status.demo;
  const url=state.status.qbit_public_url;$("open-qbit").hidden=!url;if(url)$("open-qbit").href=url;
  $("stat-downloads").textContent=state.torrentError?"—":state.torrents.length;$("download-count").textContent=state.torrents.length;$("request-count").textContent=state.requests.filter(r=>r.status!=="complete").length;$("stat-review").textContent=ready().length;$("stat-library").textContent=state.library.length;$("stat-free").textContent=size(state.status.free_bytes);
  $("content").innerHTML=({overview:torrentTable,requests:requestTable,downloads:torrentTable,staging:stagingTable,library:libraryTable,history:historyTable,settings:settingsPanel}[tab])();
  $("reviews").innerHTML=ready().length?ready().map(j=>`<div class="review-row"><div><b>${esc(label(j))}</b><p>${j.result.files.length} files · ${size(j.result.bytes)} · ${j.result.warnings.length?"Review notes included":"Validation complete"}</p></div><button class="mini" data-action="review" data-id="${j.id}">Review import →</button></div>`).join(""):empty("Nothing needs your approval yet","Validate a completed download to preview the files before import.","✓");
}
function openReview(id){
  const job=state.jobs.find(j=>j.id===id);if(!job?.result)return;
  activeReview=job;const r=job.result;
  $("review-details").innerHTML=`<p class="muted">${esc(r.torrent_check)}</p>${r.warnings.map(w=>`<div class="notice">${esc(w)}</div>`).join("")}<div class="file-list">${r.files.map(f=>`<div class="file-row">${esc(f.output)}<small>${size(f.snapshot.size)} · ${f.media?esc(f.media.validation)+" · "+esc(f.media.codecs.join(", ")):"Companion file"}</small><small>SHA-256 ${esc(f.sha256)}</small></div>`).join("")}</div>${r.skipped.length?`<details><summary>Excluded files (${r.skipped.length})</summary><p class="muted">${r.skipped.map(esc).join("<br>")}</p></details>`:""}`;
  const name=label(job).split("/").pop().replace(/\.(mkv|mp4|avi|mov|webm|m4v)$/i,"");$("destination").value=name;updateDestination();$("review-dialog").showModal();
}
function updateDestination(){$("destination-preview").textContent=`${state.status?.media||"/media"}/${$("category").value}/${$("destination").value||"…"}`;}
$("category").addEventListener("change",updateDestination);$("destination").addEventListener("input",updateDestination);
document.addEventListener("click",async e=>{
  const button=e.target.closest("[data-action]");if(!button)return;const {action,id}=button.dataset;
  if(action==="review"){openReview(id);return;}
  button.disabled=true;
  try{
    if(action==="validate-torrent")await api("validate",{torrent_hash:id});
    else if(action==="validate-source")await api("validate",{source:id});
    else if(action==="audit")await api(`library/${id}/audit`,{});
    else if(action==="attach-request"){
      const hash=$("torrent-"+id).value;if(!hash)throw new Error("Choose a qBittorrent download first.");
      await api(`requests/${id}/attach`,{torrent_hash:hash});
    } else await api("torrents/action",{torrent_hash:id,action});
    toast(action.startsWith("validate")?"Validation queued. Full media checks can take a while; follow progress in Activity.":action==="recheck"?"Recheck requested. Wait for qBittorrent to finish before validating.":"Action queued. Follow its result in Activity.");await refresh();
  }catch(error){toast(error.message);}finally{button.disabled=false;}
});
$("import-form").addEventListener("submit",async e=>{
  e.preventDefault();const button=e.submitter;button.disabled=true;
  try{await api("import",{validation_id:activeReview.id,category:$("category").value,name:$("destination").value.trim()});$("review-dialog").close();toast("Import queued. Your source files will stay in staging.");await refresh();}catch(error){toast(error.message);}finally{button.disabled=false;}
});
$("add-magnet").addEventListener("click",()=>$("magnet-dialog").showModal());
$("magnet-form").addEventListener("submit",async e=>{
  e.preventDefault();const button=e.submitter;button.disabled=true;
  try{await api("torrents/add",{magnet:$("magnet").value.trim(),category:$("magnet-category").value.trim()});$("magnet-dialog").close();$("magnet").value="";toast("Magnet submission queued. Check Activity for qBittorrent’s response.");await refresh();}catch(error){toast(error.message);}finally{button.disabled=false;}
});
$("new-request").addEventListener("click",()=>$("request-dialog").showModal());
$("request-form").addEventListener("submit",async e=>{
  e.preventDefault();const button=e.submitter;button.disabled=true;
  try{await api("requests",{query:$("request-query").value.trim(),media_type:$("request-type").value,title:$("request-title").value.trim()||null});$("request-dialog").close();$("request-query").value="";$("request-title").value="";tab="requests";toast("Request created. Fox Den will follow it through validation and import.");await refresh();}catch(error){toast(error.message);}finally{button.disabled=false;}
});
api("session").then(()=>unlock()).catch(()=>{});setInterval(()=>{if(!document.hidden)refresh();},10000);
