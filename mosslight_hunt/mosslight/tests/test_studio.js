"use strict";
// Dependency-free DOM contract tests for the studio. No network or browser is used.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const root = path.join(__dirname, "..", "mosslight", "static");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
class Element {
  constructor(id) { this.id=id;this.value="";this.checked=false;this.disabled=false;this.children=[];this.listeners={};this.style={};this.dataset={};this.classList={remove(){},add(){}}; }
  addEventListener(name, handler) {this.listeners[name]=handler;}
  append(...children) {this.children.push(...children);}
  appendChild(child) {this.append(child);}
  replaceChildren(...children) {this.children=[...children];}
  querySelectorAll() {return [];}
  setAttribute(key,value) {this[key]=value;}
  click() {if(this.listeners.click)return this.listeners.click({});}
}
const elements = new Map([...html.matchAll(/id="([^"]+)"/g)].map(match=>[match[1],new Element(match[1])]));
assert.equal(elements.size,[...html.matchAll(/id="([^"]+)"/g)].length,"IDs must be unique");
const actionButtons = [...html.matchAll(/data-action="([^"]+)"/g)].map(match=>{const e=new Element();e.dataset.action=match[1];return e;});
const defaults={"map-layer":"art","brush-radius":"0","brush-shape":"diamond","recipe":"mulch","seed-species":"moss","history-metric":"moisture","note-search":"","note-tags":"","seed":"7"};
for(const [id,value] of Object.entries(defaults))elements.get(id).value=value;
const world={width:4,height:4,day:0,revision:0,seed:7,journal:[],cells:Array.from({length:16},()=>({moisture:50,nutrients:50,shade:50,species:null,age:0,vitality:0})),workbench:{tiles:Array.from({length:16},()=>({terrain:"soil",mulch:0,stress:0,structure:"none"})),inventory:{fiber:0},seeds:{moss:0},notes:[],tasks:[],specimens:[],plans:[],rules:[],beds:[],nursery:[]}};
const state={world,summary:{season:"Dawn",weather:"clear",population:{moss:0,fern:0,clover:0,glowcap:0},average_moisture:50,average_nutrients:50},undo:0,redo:0};
const requests=[];
const context=vm.createContext({
  document:{getElementById(id){assert(elements.has(id),`Missing HTML element ${id}`);return elements.get(id);},querySelectorAll(selector){return selector==="[data-action]"?actionButtons:[];},querySelector(){return null;},createElement(){return new Element();}},
  fetch:async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>structuredClone(state),text:async()=>'<svg xmlns="http://www.w3.org/2000/svg"></svg>'};},
  setTimeout,clearTimeout,setInterval,clearInterval,URL,Blob,console
});
vm.runInContext(fs.readFileSync(path.join(root,"app.js"),"utf8"),context);
function evaluate(source){return vm.runInContext(source,context);}
async function run(){
  await new Promise(setImmediate);
  assert.equal(elements.get("season-badge").textContent,"DAY 000 / DAWN");
  assert(actionButtons.every(button=>button.disabled),"Tending needs a selection");
  evaluate("select(0,0)");
  assert(actionButtons.every(button=>!button.disabled));
  assert.equal(elements.get("coordinates").textContent,"◉   TILE 1, 1");
  elements.get("brush-radius").value="1";
  assert.equal(JSON.stringify(evaluate("brushTiles()")),"[[0,0],[1,0],[0,1]]");
  elements.get("brush-shape").value="square";
  assert.equal(evaluate("brushTiles().length"),4);
  await actionButtons.find(b=>b.dataset.action==="water").click();
  const edit=requests.find(r=>r.url==="/api/command");
  const payload=JSON.parse(edit.options.body);
  assert.equal(payload.revision,0);
  assert.equal(payload.command.op,"tend_many");
  assert.equal(payload.command.args.tiles.length,4);
  elements.get("brush-radius").value="-1";
  await actionButtons[0].click();
  assert.match(elements.get("status").textContent,/radius/);
  elements.get("note-text").value="<b>wet moss</b>";
  elements.get("note-tags").value=" damp, pond ";
  await elements.get("note-form").listeners.submit({preventDefault(){}});
  const note=JSON.parse(requests.filter(r=>r.url==="/api/command").at(-1).options.body);
  assert.equal(note.command.args.content,"<b>wet moss</b>");
  assert.deepEqual(note.command.args.labels,["damp","pond"]);
  assert.equal(note.command.args.tile,null);
  state.world.workbench.notes=[{id:1,day:0,text:"<script>literal note</script>",tags:[]}];
  await evaluate("refresh()");
  const rendered=elements.get("notes-list").children[0].children[0];
  assert.equal(rendered.textContent,"Day 0 · <script>literal note</script> ");
  assert.equal(rendered.innerHTML,undefined,"Authored text must remain text");
  console.log("Studio DOM contracts passed: initialization, selection, brush, mutation, error feedback, notes, text safety.");
}
run().catch(error=>{console.error(error);process.exitCode=1;});
