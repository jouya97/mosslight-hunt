"use strict";
const $ = (id) => document.getElementById(id);
let snapshot = null;
let selected = null;
let timer = null;
let busy = false;
const names = {moss:"Moss",fern:"Fern",clover:"Clover",glowcap:"Glowcap"};
const status = (message) => { $("status").textContent = message; };
async function request(path, body) {
  const response = await fetch(path, body === undefined ? undefined : {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "The garden could not respond.");
  return data;
}
async function refresh() {
  snapshot = await request("/api/world");
  await display();
}
async function display() {
  const {world, summary} = snapshot;
  $("season-badge").textContent = `DAY ${String(world.day).padStart(3,"0")} / ${summary.season.toUpperCase()}`;
  $("weather-badge").textContent = `${({clear:"☼",drizzle:"◌",rain:"☂",storm:"☁"})[summary.weather]}  ${summary.weather.toUpperCase()}`;
  const svg = await fetch(`/api/svg?layer=${encodeURIComponent($("map-layer").value)}`).then((response) => response.text());
  $("garden").innerHTML = svg;
  $("garden").querySelectorAll(".tile").forEach((tile) => {
    tile.addEventListener("click", () => select(Number(tile.dataset.x), Number(tile.dataset.y)));
    tile.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") {event.preventDefault();select(Number(tile.dataset.x), Number(tile.dataset.y));} });
  });
  $("population").replaceChildren();
  Object.entries(summary.population).forEach(([species, count]) => {
    const block = document.createElement("div");
    block.textContent = names[species];
    const number = document.createElement("strong");
    number.textContent = count;
    block.appendChild(number);
    $("population").appendChild(block);
  });
  $("averages").textContent = `Average moisture ${summary.average_moisture}% · soil nutrients ${summary.average_nutrients}%.`;
  $("journal").replaceChildren();
  [...world.journal].reverse().slice(0,10).forEach((entry) => {
    const item = document.createElement("li");
    const day = document.createElement("span"); day.textContent = `DAY ${String(entry.day).padStart(3,"0")}`;
    const message = document.createElement("div"); message.textContent = entry.text;
    item.append(day,message); $("journal").appendChild(item);
  });
  if (selected && (selected.x >= world.width || selected.y >= world.height)) selected = null;
  updateSelection();
  displayWorkbench();
}
function select(x,y) {selected={x,y};updateSelection();displayWorkbench();}
function updateSelection() {
  const world = snapshot?.world;
  document.querySelectorAll(".tile.selected").forEach((tile) => tile.classList.remove("selected"));
  document.querySelectorAll("[data-action]").forEach((button) => button.disabled = !selected || busy);
  if (!selected || !world) {
    $("tile-title").textContent = "Choose a little place";
    $("tile-description").textContent = "Select a tile in the terrarium to see what lives there.";
    $("coordinates").textContent = "◉   NO TILE SELECTED";
    for (const metric of ["moisture","nutrients","shade"]) { $(metric+"-value").textContent="—"; $(metric+"-meter").style.width="0%"; }
    return;
  }
  const {x,y} = selected;
  const cell = world.cells[y*world.width+x];
  $("tile-title").textContent = cell.species ? `${names[cell.species]} in the ${cell.shade>55?"shade":"light"}` : "A patch of open earth";
  $("tile-description").textContent = cell.species ? `Age ${cell.age} days · vitality ${cell.vitality}%. This patch has room to change.` : "The soil is ready for a seed, or for whatever wanders in.";
  $("coordinates").textContent = `◉   TILE ${x+1}, ${y+1}`;
  for (const metric of ["moisture","nutrients","shade"]) {$(metric+"-value").textContent=cell[metric]+"%";$(metric+"-meter").style.width=cell[metric]+"%";}
  const tile = document.querySelector(`.tile[data-x="${x}"][data-y="${y}"]`);
  tile?.classList.add("selected");
}
async function mutate(path, body) {
  if (busy) return;
  busy=true;
  document.querySelectorAll("button").forEach((button) => button.disabled=true);
  try {snapshot=await request(path,{...body,revision:snapshot?.world.revision});await display();status("The garden has changed.");}
  catch(error){status(error.message); if (error.message.includes("refresh")) await refresh();}
  finally {busy=false;document.querySelectorAll("button").forEach((button)=>button.disabled=false);updateSelection();displayWorkbench();}
}
function download(filename,content,mime){const url=URL.createObjectURL(new Blob([content],{type:mime}));const link=document.createElement("a");link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$("day-one").addEventListener("click",()=>mutate("/api/step",{days:1}));
$("day-week").addEventListener("click",()=>mutate("/api/step",{days:7}));
$("autoplay").addEventListener("click",()=>{
  if(timer){clearInterval(timer);timer=null;$("autoplay").textContent="▶   START SLOW TIME";}
  else{timer=setInterval(()=>mutate("/api/step",{days:1}),1800);$("autoplay").textContent="Ⅱ   PAUSE SLOW TIME";}
});
document.querySelectorAll("[data-action]").forEach((button)=>button.addEventListener("click",safe(()=>{if(selected)return command("tend_many",{tiles:brushTiles(),action:button.dataset.action});})));
$("save-json").addEventListener("click",()=>download(`mosslight-day-${snapshot.world.day}.json`,JSON.stringify(snapshot.world,null,2)+"\n","application/json"));
$("save-svg").addEventListener("click",async()=>{const svg=await fetch(`/api/svg?layer=${encodeURIComponent($("map-layer").value)}`).then((response)=>response.text());download(`mosslight-day-${snapshot.world.day}.svg`,svg,"image/svg+xml");});
$("load-json").addEventListener("click",()=>$("file-input").click());
$("file-input").addEventListener("change",async(event)=>{
  const file=event.target.files[0];if(!file)return;
  try{const world=JSON.parse(await file.text());snapshot=await request("/api/import",{world,revision:snapshot?.world.revision});selected=null;await display();status("A saved garden has opened.");}
  catch(error){status(`Could not open garden: ${error.message}`);} event.target.value="";
});
$("new-garden").addEventListener("click",()=>{const seed=Number($("seed").value);if(!Number.isSafeInteger(seed)){status("Enter a whole-number seed.");return;} selected=null;mutate("/api/new",{seed});});


const value = (id) => $(id).value;
const number = (id) => Number(value(id));
function command(op,args){return mutate("/api/command",{command:{op,args}});}
function atTile(op,args={}){
  if(!selected){status("Select a garden tile first.");return;}
  return command(op,{...selected,...args});
}
function brushTiles(){
  if(!selected)throw new Error("Select a garden tile first.");
  const radius=number("brush-radius"),shape=value("brush-shape"),points=[];
  if(!Number.isInteger(radius)||radius<0||radius>8)throw new Error("Brush radius must be 0–8.");
  for(let y=Math.max(0,selected.y-radius);y<=Math.min(snapshot.world.height-1,selected.y+radius);y++){
    for(let x=Math.max(0,selected.x-radius);x<=Math.min(snapshot.world.width-1,selected.x+radius);x++){
      const dx=Math.abs(x-selected.x),dy=Math.abs(y-selected.y);
      if(shape==="diamond"&&dx+dy>radius)continue;
      if(shape==="circle"&&dx*dx+dy*dy>radius*radius)continue;
      points.push([x,y]);
    }
  }
  return points;
}
function entryList(id,entries,label,actions=[]){
  const container=$(id);container.replaceChildren();
  if(!entries.length){const p=document.createElement("p");p.className="hint";p.textContent="Nothing here yet.";container.append(p);return;}
  entries.forEach(entry=>{
    const row=document.createElement("div"),text=document.createElement("span");row.className="entry";text.textContent=label(entry);row.append(text);
    actions.forEach(action=>{if(action.when&&!action.when(entry))return;const button=document.createElement("button");button.textContent=typeof action.label==="function"?action.label(entry):action.label;button.addEventListener("click",()=>action.run(entry));row.append(button);});container.append(row);
  });
}
function displayWorkbench(){
  if(!snapshot)return;
  const state=snapshot.world.workbench;
  $("undo").disabled=busy||!snapshot.undo;$("redo").disabled=busy||!snapshot.redo;
  $("inventory").textContent="Materials: "+Object.entries(state.inventory).map(([k,v])=>`${k} ${v}`).join(" · ")+" | Seeds: "+Object.entries(state.seeds).map(([k,v])=>`${k} ${v}`).join(" · ");
  const query=value("note-search").toLocaleLowerCase();
  const notes=state.notes.filter(n=>query.startsWith("#")?n.tags.includes(query.slice(1)):n.text.toLocaleLowerCase().includes(query));
  entryList("notes-list",[...notes].reverse(),n=>`Day ${n.day} · ${n.text} ${n.tags.map(t=>"#"+t).join(" ")}`,[{label:"Delete",run:n=>command("delete_entry",{collection:"notes",ident:n.id})}]);
  entryList("tasks-list",[...state.tasks].sort((a,b)=>a.due-b.due||a.id-b.id),t=>`${t.done?"✓":"○"} Day ${t.due}: ${t.text}`,[{label:t=>t.done?"Reopen":"Complete",run:t=>command("complete_task",{ident:t.id,done:!t.done})}]);
  entryList("specimens-list",state.specimens,s=>`${s.label} · ${names[s.species]} · day ${s.day} · vitality ${s.vitality}%`);
  entryList("plans-list",state.plans,p=>`${p.name} · day ${p.day} · ${p.status} · ${p.remaining} runs left${p.last_error?" · "+p.last_error:""}`,[{label:"Cancel",when:p=>p.status==="pending",run:p=>command("cancel_plan",{ident:p.id})}]);
  entryList("rules-list",state.rules,r=>`${r.name}: ${r.metric} ${r.operator} ${r.threshold} → ${r.action}`,[{label:r=>r.enabled?"Disable":"Enable",run:r=>command("enable_rule",{ident:r.id,enabled:!r.enabled})},{label:"Delete",run:r=>command("delete_rule",{ident:r.id})}]);
  entryList("beds-list",state.beds,b=>`${b.name} · ${b.tiles.length} tiles`,[{label:"Water",run:b=>command("tend_many",{tiles:b.tiles,action:"water"})},{label:"Delete",run:b=>command("delete_bed",{ident:b.id})}]);
  entryList("nursery-list",state.nursery,n=>`Batch ${n.id}: ${names[n.species]} × ${n.count} · ${n.status} · water ${n.hydration}/3 · vitality ${n.vitality}%`,[
    {label:"Water",when:n=>["growing","ready"].includes(n.status),run:n=>command("nursery_water",{ident:n.id})},
    {label:"Plant at selected tile",when:n=>n.status==="ready",run:n=>atTile("plant_out",{ident:n.id})},
    {label:"Discard",when:n=>!["discarded","planted"].includes(n.status),run:n=>command("nursery_discard",{ident:n.id})}]);
  if(selected){const tile=state.tiles[selected.y*snapshot.world.width+selected.x];$("tile-habitat").textContent=`Selected habitat: ${tile.terrain} · ${tile.structure} · mulch ${tile.mulch} · stress ${tile.stress}`;}
}
function safe(handler){return async(event)=>{try{await handler(event);}catch(error){status(error.message);}};}
function form(id,handler){$(id).addEventListener("submit",safe(async event=>{event.preventDefault();await handler();}));}
$("map-layer").addEventListener("change",safe(display));
$("undo").addEventListener("click",()=>mutate("/api/undo",{}));
$("redo").addEventListener("click",()=>mutate("/api/redo",{}));
document.querySelectorAll("[data-panel]").forEach(button=>button.addEventListener("click",()=>{
  document.querySelectorAll(".work-panel").forEach(panel=>panel.hidden=panel.id!=="panel-"+button.dataset.panel);
  document.querySelectorAll("[data-panel]").forEach(tab=>tab.setAttribute("aria-pressed",String(tab===button)));
  if(button.dataset.panel==="laboratory")loadHistory().catch(error=>status(error.message));
}));
$("set-terrain").addEventListener("click",()=>atTile("terrain",{terrain:value("terrain-choice")}));
$("set-structure").addEventListener("click",()=>atTile("structure",{structure:value("structure-choice")}));
$("set-shade").addEventListener("click",()=>atTile("shade",{shade:number("shade-choice")}));
$("prune").addEventListener("click",()=>atTile("prune"));
$("harvest").addEventListener("click",()=>atTile("harvest"));
$("collect-seed").addEventListener("click",()=>atTile("collect_seed"));
$("press-specimen").addEventListener("click",()=>atTile("specimen"));
$("sow").addEventListener("click",()=>atTile("sow",{species:value("seed-species")}));
$("craft").addEventListener("click",()=>command("craft",{recipe:value("recipe")}));
$("apply-material").addEventListener("click",()=>atTile("apply_material",{material:value("recipe")}));
form("note-form",()=>{
  if($("note-at-tile").checked&&!selected)throw new Error("Select a tile to attach this observation.");
  return command("note",{content:value("note-text"),labels:value("note-tags").split(",").map(t=>t.trim()).filter(Boolean),tile:$("note-at-tile").checked?[selected.x,selected.y]:null});
});
$("note-search").addEventListener("input",displayWorkbench);
form("task-form",()=>command("task",{content:value("task-text"),due:number("task-due")}));
form("plan-form",()=>command("schedule",{name:value("plan-name"),day:number("plan-day"),repeat:number("plan-repeat"),runs:number("plan-runs"),action:value("plan-action"),tiles:brushTiles()}));
form("rule-form",()=>command("rule",{name:value("rule-name"),metric:value("rule-metric"),operator:value("rule-operator"),threshold:number("rule-threshold"),action:value("rule-action"),tiles:brushTiles()}));
form("bed-form",()=>command("bed",{name:value("bed-name"),tiles:brushTiles()}));
async function loadHistory(){const response=await fetch(`/api/history.svg?metric=${encodeURIComponent(value("history-metric"))}`);if(!response.ok)throw new Error("Could not load history.");$("history-chart").innerHTML=await response.text();}
$("history-metric").addEventListener("change",safe(loadHistory));
$("show-report").addEventListener("click",safe(async()=>{
  const report=await request("/api/report");
  $("field-report").textContent=`${report.title}: ${report.census.coverage}% covered, ${report.census.richness} species, ${report.patches.length} connected patches. Visitors: ${report.visitors.bees} bees, ${report.visitors.fireflies} fireflies, ${report.visitors.worms} worms. ${report.alerts.length} tiles need attention; ${report.due_tasks.length} tasks are due.`;
  $("lab-output").textContent=JSON.stringify(report,null,2);await loadHistory();
}));
$("show-forecast").addEventListener("click",safe(async()=>{const result=await request("/api/forecast?days=7");delete result.world;$("lab-output").textContent=JSON.stringify(result,null,2);status("Forecast complete; your garden is unchanged.");}));
$("show-advice").addEventListener("click",safe(async()=>{$("lab-output").textContent=JSON.stringify(await request(`/api/recommend?species=${value("seed-species")}`),null,2);}));
$("show-guide").addEventListener("click",safe(async()=>{$("lab-output").textContent=JSON.stringify(await request("/api/catalog"),null,2);}));
$("run-command").addEventListener("click",safe(()=>mutate("/api/command",{command:JSON.parse(value("command-json"))})));
for(const [id,path,name,mime] of [["save-csv","/api/survey.csv","survey.csv","text/csv"],["save-notebook","/api/notebook.md","notebook.md","text/markdown"]]){
  $(id).addEventListener("click",safe(async()=>{const response=await fetch(path);if(!response.ok)throw new Error("Export failed.");download(name,await response.text(),mime);}));
}
$("take-cutting").addEventListener("click",()=>atTile("cutting"));
$("start-nursery").addEventListener("click",()=>command("nursery_seed",{species:value("seed-species")}));
$("show-calendar").addEventListener("click",safe(async()=>{$("lab-output").textContent=JSON.stringify(await request("/api/calendar"),null,2);}));
$("show-almanac").addEventListener("click",safe(async()=>{$("lab-output").textContent=JSON.stringify(await request("/api/almanac"),null,2);}));
$("show-experiment").addEventListener("click",safe(async()=>{
  if(!selected)throw new Error("Select a tile for the shade experiment.");
  const result=await request("/api/experiment",{days:7,every:7,treatments:[{name:"Shade cloth",events:[{offset:0,command:{op:"structure",args:{...selected,structure:"shade_cloth"}}}]}]});
  $("lab-output").textContent=JSON.stringify(result,null,2);status("Experiment complete; your garden is unchanged.");
}));
refresh().catch((error)=>status(error.message));
