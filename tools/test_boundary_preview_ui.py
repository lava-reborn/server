"""Run the real preview browser script in an isolated DOM, without a browser session."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from boundary_preview_page import PAGE
from testkit import run_cases

HARNESS=r"""
const vm=require('node:vm'),assert=require('node:assert/strict'),fs=require('node:fs');
const source=fs.readFileSync(0,'utf8');
class Context {constructor(){this.globalAlpha=1;this.calls=[];this.strokes=[];}clearRect(){this.calls=[];this.strokes=[];}fillRect(...args){this.calls.push([this.fillStyle,this.globalAlpha,...args]);}drawImage(){}strokeRect(...args){this.strokes.push([...args,this.strokeStyle]);}beginPath(){}lineTo(){}moveTo(){}stroke(){}}
class Element {constructor(id=''){this.id=id;this.value=id==='opacity'?70:id==='zoom'?100:1;this.checked=true;this.style={};this.children=[];this.ctx=new Context();this.clientWidth=500;this.clientHeight=400;}
 set src(value){this._src=value;this.srcCount=(this.srcCount||0)+1;}get src(){return this._src;}
 setPointerCapture(){}getContext(){return this.ctx;}addEventListener(name,fn){this[name]=fn;}setAttribute(name,value){this.attrs??={};this.attrs[name]=String(value);}getAttribute(name){return this.attrs?.[name]??null;}replaceChildren(...nodes){this.children=nodes;}append(...nodes){this.children.push(...nodes);}add(node){this.children.push(node);}getBoundingClientRect(){return {left:0,top:0,width:64,height:128};}}
const elements={},el=id=>elements[id]??=(new Element(id));
const fixture={bounds:[0,0,10,10],water:['2,1','2,2'],rocks:['3,3'],blocked:['1,1','2,1','2,2','3,3'],passable:['4,4'],overrides:{},opacity:70,revision:'r1',settlements:{},catalog:{18:{name:'native',kind:'coast',closed:['S']},10:{name:'rock',kind:'rock',closed:['N']}},source:{sha256:'snapshot123456789'},plan:{effective_water:['2,2'],replaced_water:['2,1'],retained_river:['2,2'],generated_walls:['3,4'],placements:{'2,1':{template:18,kind:'coast',replaces:'water',closed:['S'],allowed_exits:['N','E','W']},'3,3':{template:10,kind:'rock',closed:['N'],allowed_exits:['E','S','W']}},issues:[],summary:{water:1,walls:1,coast:1,rock_locations:1,unresolved:0,added_walls:0}}};
const windowHandlers={};const pending=[];const context=vm.createContext({console,document:{getElementById:el,createElement:()=>new Element(),createElementNS:()=>new Element()},window:{addEventListener(name,fn){windowHandlers[name]=fn;}},Option:function(label,value){this.label=label;this.value=value;},fetch:async(path,options)=>{if(path==='/state')return {ok:true,json:async()=>fixture};if(path.startsWith('/mob-sprite-info'))return {ok:true,json:async()=>({url:'/mob-sprite?type=123',width:40,height:80,ox:-20,oy:-80})};if(path.startsWith('/cell?'))return {ok:true,json:async()=>({actual:{id:30,title:'Пустыня',name:'native',width:64,height:128,spawns:[]},draft_exits:['N','E','S','W'],neighbours:{}})};return new Promise(resolve=>pending.push({path,body:JSON.parse(options.body),resolve}));}});
const run=code=>vm.runInContext(code,context);
async function reply(data){const request=pending.shift();assert.ok(request,'expected pending request');request.resolve({ok:true,json:async()=>data});await new Promise(resolve=>setImmediate(resolve));return request;}
(async()=>{
 run(source);await new Promise(resolve=>setImmediate(resolve));
 assert.equal(run('S.revision'),'r1');
 el('neighbourSection').open=false;run('showNeighbours("1,2")');assert.equal(el('neighbours').children.length,0);
 el('neighbourSection').open=true;run('showNeighbours("1,2")');assert.equal(el('neighbours').children.length,9);el('neighbourSection').open=false;
 assert.equal(run('MODES.includes("coast")'),true);assert.equal(run('MODES.includes("open")'),false);assert.equal(run('payload().passable.length'),0);assert.equal(run('layers.open'),undefined);
 // Display toggles cannot remove layers from a saved payload.
 const before=run('JSON.stringify(payload())');el('showauto').checked=false;el('showauto').onchange();assert.equal(run('JSON.stringify(payload())'),before);assert.equal(run('dirty'),false);
 // In auto view, a replaced water cell is painted only as coast; the input water mask stays intact.
 el('showauto').checked=true;el('showauto').onchange();const insetCanvas=run('cache');
 assert.equal(insetCanvas.ctx.calls.filter(v=>v[2]===12&&v[3]===6).length,1);
 assert.equal(insetCanvas.ctx.calls.find(v=>v[2]===12&&v[3]===6)[0],'rgba(15,105,55,.8)');
 assert.equal(run('payload().water.includes("2,1")'),true);
 el('colorCoast').checked=false;el('colorCoast').onchange();assert.equal(insetCanvas.ctx.calls.some(v=>v[2]===12&&v[3]===6),false);el('colorCoast').checked=true;el('colorCoast').onchange();
 el('showauto').checked=false;el('showauto').onchange();assert.equal(insetCanvas.ctx.calls.find(v=>v[2]===12&&v[3]===6)[0],'rgba(60,120,200,.55)');
 // A manual water mark is painted exactly once and in the same colour with/without auto.
 el('showauto').checked=true;el('showauto').onchange();const canvas=run('cache');let marks=canvas.ctx.calls.filter(v=>v[2]===12&&v[3]===12);assert.equal(marks.length,1);assert.equal(marks[0][0],'rgba(60,120,200,.55)');
 el('showauto').checked=false;el('showauto').onchange();assert.deepEqual(canvas.ctx.calls.filter(v=>v[2]===12&&v[3]===12),marks);
 // Generated walls replace the display colour only and never become manual walls.
 assert.equal(run('layers.wall.has("3,4")'),false);assert.equal(run('payload().blocked.includes("3,4")'),false);
 el('showauto').checked=true;el('showauto').onchange();assert.equal(canvas.ctx.calls.find(v=>v[2]===18&&v[3]===24)[0],'rgba(255,36,36,.75)');
 el('showauto').checked=false;el('showauto').onchange();assert.equal(canvas.ctx.calls.some(v=>v[2]===18&&v[3]===24),false);
 // Each colour can be hidden independently without changing the terrain payload or geometry.
 el('showauto').checked=true;el('showauto').onchange();
 const originalPaint=JSON.stringify(canvas.ctx.calls),originalPayload=run('JSON.stringify(payload())'),originalGeometry=run('geomVersion');
 for(const [name,id] of Object.entries(run('COLOR_SWITCH'))){
  const colour=run('COLORS['+JSON.stringify(name)+']');el(id).checked=false;el(id).onchange();
  assert.equal(canvas.ctx.calls.some(v=>v[0]===colour),false,name);
  assert.equal(run('JSON.stringify(payload())'),originalPayload);assert.equal(run('geomVersion'),originalGeometry);assert.equal(run('dirty'),false);
  el(id).checked=true;el(id).onchange();assert.equal(JSON.stringify(canvas.ctx.calls),originalPaint);
 }
 el('colorIssues').checked=false;el('colorIssues').onchange();assert.equal(run('JSON.stringify(payload())'),originalPayload);el('colorIssues').checked=true;el('colorIssues').onchange();
 // Painting any colour preserves all untouched generated colours until recalculation.
 const paintSaved=run('({layers:Object.fromEntries(Object.entries(layers).map(([k,v])=>[k,new Set(v)])),overrides:{...overrides},dirty,editVersion,geomVersion,planVersion,mode,last})');
 const colourAt=(x,y)=>run('cache').ctx.calls.find(v=>v[2]===x*6&&v[3]===y*6)?.[0];
 for(const colour of ['wall','water','rocks','coast','erase']){
  run('mode='+JSON.stringify(colour)+';if(stamp(3,3))changed();');
  assert.equal(colourAt(3,4),'rgba(255,36,36,.75)','unmodified generated wall stays red: '+colour);
  assert.equal(colourAt(2,2),'rgba(60,120,200,.55)','unmodified water stays blue: '+colour);
  assert.equal(colourAt(2,1),'rgba(15,105,55,.8)','unmodified shore stays green: '+colour);
  assert.equal(colourAt(3,3),colour==='erase'?undefined:run('COLORS['+JSON.stringify(colour)+']'));
  assert.equal(run('Object.values(layers).filter(s=>s.has("3,3")).length'),colour==='erase'?0:1);
 }
 // Recolouring resets an old native-template override; undo restores both.
 run('layers.rocks.add("3,3");overrides["3,3"]=10;mode="wall";');
 el('over').pointerdown({button:0,clientX:19,clientY:19,pointerId:4});windowHandlers.pointerup();
 assert.equal(run('overrides["3,3"]'),undefined);assert.equal(run('layers.wall.has("3,3")'),true);
 el('undo').onclick();assert.equal(run('overrides["3,3"]'),10);assert.equal(run('layers.rocks.has("3,3")'),true);
 Object.assign(context,{paintSaved});run('({dirty,editVersion,geomVersion,planVersion,mode,last}=paintSaved);layers=Object.fromEntries(Object.entries(paintSaved.layers).map(([k,v])=>[k,new Set(v)]));overrides={...paintSaved.overrides};render();');
 // Erasing an automatic shore keeps the river core and records suppression.
 run('mode="erase";');el('over').pointerdown({button:0,clientX:13,clientY:7,pointerId:5});
 el('over').pointermove({clientX:13.2,clientY:7.2});el('over').pointermove({clientX:13.5,clientY:7.5});windowHandlers.pointerup();
 assert.equal(run('overrides["2,1"]'),null);assert.equal(run('layers.water.has("2,1")'),true);
 assert.equal(colourAt(2,1),'rgba(60,120,200,.55)');
 el('undo').onclick();assert.equal(run('overrides["2,1"]'),undefined);assert.equal(run('layers.water.has("2,1")'),true);
 // A manually painted shore can also be erased, with no automatic return.
 run('mode="coast";stamp(1,2);mode="erase";stamp(1,2);');
 assert.equal(run('layers.coast.has("1,2")'),false);assert.equal(run('overrides["1,2"]'),null);
 Object.assign(context,{paintSaved});run('({dirty,editVersion,geomVersion,planVersion,mode,last}=paintSaved);layers=Object.fromEntries(Object.entries(paintSaved.layers).map(([k,v])=>[k,new Set(v)]));overrides={...paintSaved.overrides};render();');
 // Manual walls and generated walls (including those backed by raw rocks)
 // can be erased; undo restores the original input and display.
 for(const [x,y,manual] of [[1,1,true],[3,4,false]]){
  run('mode="erase";');el('over').pointerdown({button:0,clientX:x*6+1,clientY:y*6+1,pointerId:6});windowHandlers.pointerup();
  assert.equal(run('overrides['+JSON.stringify(x+','+y)+']'),null);assert.equal(colourAt(x,y),undefined);
  if(manual)assert.equal(run('layers.wall.has("1,1")'),false);
  el('undo').onclick();assert.equal(colourAt(x,y),'rgba(255,36,36,.75)');
 }
 run('layers.rocks.add("3,4");capturePlan();mode="erase";');
 el('over').pointerdown({button:0,clientX:19,clientY:25,pointerId:7});windowHandlers.pointerup();
 assert.equal(run('layers.rocks.has("3,4")'),false);assert.equal(run('overrides["3,4"]'),null);assert.equal(colourAt(3,4),undefined);
 el('undo').onclick();assert.equal(run('layers.rocks.has("3,4")'),true);assert.equal(colourAt(3,4),'rgba(255,36,36,.75)');
 Object.assign(context,{paintSaved});run('({dirty,editVersion,geomVersion,planVersion,mode,last}=paintSaved);layers=Object.fromEntries(Object.entries(paintSaved.layers).map(([k,v])=>[k,new Set(v)]));overrides={...paintSaved.overrides};capturePlan();render();');
 const noopVersion=run('geomVersion');run('mode="wall";last=null;paint({clientX:7,clientY:7});mode="inspect";');assert.equal(run('geomVersion'),noopVersion);
 // A view setting does not invalidate geometry, including at maximum opacity.
 el('opacity').value=100;el('opacity').oninput({target:el('opacity')});assert.equal(run('geomVersion'),run('planVersion'));
 assert.ok(canvas.ctx.calls.every(v=>v[0].includes('rgba(')&&v[0].includes(',.')));
 // Middle-button drag pans the view and cannot paint terrain or mark it dirty.
 const panPayload=run('JSON.stringify(payload())'),panGeometry=run('geomVersion');
 el('wrap').scrollLeft=100;el('wrap').scrollTop=80;let prevented=false;
 el('over').pointerdown({button:1,clientX:300,clientY:200,pointerId:1,preventDefault(){prevented=true;}});
 el('over').pointermove({clientX:240,clientY:150});assert.equal(prevented,true);
 assert.equal(el('wrap').scrollLeft,160);assert.equal(el('wrap').scrollTop,130);
 assert.equal(run('JSON.stringify(payload())'),panPayload);assert.equal(run('geomVersion'),panGeometry);
 windowHandlers.pointerup();assert.equal(run('pan'),null);assert.equal(el('over').style.cursor,'crosshair');
 // Resizing the side panel is view-only; native geometry precedes all controls.
 const resizingPayload=run('JSON.stringify(payload())'),resizingDirty=run('dirty');
 el('main').getBoundingClientRect=()=>({left:0,right:1200,width:1200});
 el('sidebar').getBoundingClientRect=()=>({width:420});
 el('resizeAside').pointerdown({button:0,pointerId:2,preventDefault(){}});
 el('resizeAside').pointermove({clientX:600});assert.equal(el('sidebar').style.width,'600px');
 el('resizeAside').pointercancel();el('resizeAside').pointermove({clientX:500});assert.equal(el('sidebar').style.width,'600px');
 el('resizeAside').keydown({key:'ArrowLeft',preventDefault(){}});assert.equal(el('sidebar').style.width,'460px');
 assert.equal(run('JSON.stringify(payload())'),resizingPayload);assert.equal(run('dirty'),resizingDirty);
 // Grid visibility and geometry size are view-only. Odd/even row picking matches native hex centres.
 run('selected="1,2";cellData={actual:{id:30,name:"native",width:64,height:128,spawns:[]}};renderCell()');
 // Shared source artwork is reused across coordinates and view toggles.
 run('cellData.actual.art_key="shared-desert";renderCell();');
 el('art').complete=true;el('art').naturalWidth=768;el('art').onload();
 const pictureURL=el('art').src,pictureLoads=el('art').srcCount;
 run('cellData.actual.id=31;renderCell();');
 assert.equal(el('art').src,pictureURL);assert.equal(el('art').srcCount,pictureLoads);
 el('showArtwork').checked=false;el('showArtwork').onchange();el('showArtwork').checked=true;el('showArtwork').onchange();
 assert.equal(el('art').srcCount,pictureLoads);assert.equal(el('art').style.display,'block');
 const hexPayload=run('JSON.stringify(payload())'),hexDirty=run('dirty');
 el('showHexes').checked=false;el('showHexes').onchange();assert.ok(el('local').src.includes('&grid=0'));
 el('showHexes').checked=true;el('showHexes').onchange();assert.ok(el('local').src.includes('&grid=1'));assert.equal(el('art').srcCount,pictureLoads);
 el('previewSize').oninput({target:{value:'720'}});assert.equal(el('local').style.height,'720px');
 for(let y=0;y<12;y++)for(let x=0;x<12;x++)assert.equal(run('JSON.stringify(hexCell({x:'+ (40*x+20*(y%2))+',y:'+ (15*y)+'}))'),JSON.stringify({x,y}));
 assert.equal(run('JSON.stringify(payload())'),hexPayload);assert.equal(run('dirty'),hexDirty);
 // Settings changed while save is in flight remain dirty.
 let save=run("$('save').onclick()");el('opacity').value=40;el('opacity').oninput({target:el('opacity')});await reply({revision:'r2'});await save;assert.equal(run('dirty'),true);assert.equal(run('S.revision'),'r2');
 save=run("$('save').onclick()");await reply({revision:'r3'});await save;assert.equal(run('dirty'),false);
 // A drag on the image resolves to a native hex and stores only per-cell draft positions.
 run('selected="1,2";cellData={actual:{id:30,name:"native",width:64,height:128,spawn_signature:"spawn-v1",spawns:[{index:0,type:123,name:"Mob",cell:65,source_cell:65}]}};S.mob_overrides={};renderCell();');
 assert.equal(el('mobX').value,1);assert.equal(el('mobY').value,1);
 const mobGeometry=run('geomVersion'),group=el('mobOverlay').children[0];
 el('moveMobs').checked=true;
 el('mobOverlay').pointerdown({button:0,pointerId:3,target:{closest(){return group;}},preventDefault(){},stopPropagation(){}});
 const scale=62/2560,event={clientX:1+80*scale,clientY:1+(126-1920*scale)/2+30*scale};
 el('mobOverlay').pointermove(event);assert.equal(group.getAttribute('transform'),'translate(80 30)');
 const dragged=el('mobOverlay').pointerup(event);const movement=pending[0];
 assert.equal(movement.path,'/validate-mobs');assert.equal(movement.body.mob_overrides['1,2'].positions[0],130);
 await reply({'1,2':{location_id:30,spawn_signature:'spawn-v1',positions:[130]}});await dragged;
 assert.equal(run('S.mob_overrides["1,2"].positions[0]'),130);assert.equal(run('geomVersion'),mobGeometry);
 assert.equal(el('mobX').value,2);assert.equal(el('mobY').value,2);
 el('resetMobs').onclick();assert.equal(run('S.mob_overrides["1,2"]'),undefined);assert.equal(run('localView().spawns[0].cell'),65);
 // Old saved positions cannot attach to a changed mob roster with the same location id.
 run('S.mob_overrides["1,2"]={location_id:30,spawn_signature:"old-roster",positions:[130]};');
 assert.equal(run('localView().spawns[0].cell'),65);el('resetMobs').onclick();
 // One move is validated at a time; a reset cancels any in-flight result.
 const lateMove=run('moveMob(0,130)');assert.equal(el('moveMob').disabled,true);
 await assert.rejects(run('moveMob(0,195)'),/предыдущего перемещения/);
 assert.equal(pending.length,1);el('resetMobs').onclick();
 await reply({'1,2':{location_id:30,spawn_signature:'spawn-v1',positions:[130]}});await lateMove;
 assert.equal(run('S.mob_overrides["1,2"]'),undefined);assert.equal(run('localView().spawns[0].cell'),65);
 assert.equal(el('moveMob').disabled,false);
 // A point correction invalidates the old plan but never edits marked water.
 el('gx').value='2';el('gy').value='1';el('goto').onclick();el('override').value='off';el('setOverride').onclick();assert.equal(run('overrides["2,1"]'),null);assert.notEqual(run('geomVersion'),run('planVersion'));assert.equal(run('layers.water.has("2,2")'),true);
 // A result for an older geometry cannot become current after a second edit.
 const calculating=run("$('calculate').onclick()");el('override').value='auto';el('setOverride').onclick();await reply(fixture.plan);await calculating;assert.notEqual(run('geomVersion'),run('planVersion'));assert.ok(el('status').textContent.includes('Нужен новый пересчёт'));
 // Manual placement mode paints a formerly generated wall as a rock immediately,
 // keeps its scene choice in the draft and never requests the global solver.
 run('S.manual_editing=true;P=JSON.parse(JSON.stringify(S.plan));layers.rocks.add("3,4");sceneEdits={};overrides={};capturePlan();mode="rocks";');
 const pendingBeforeManual=pending.length;
 el('over').pointerdown({button:0,clientX:19,clientY:25,pointerId:19});windowHandlers.pointerup();
 assert.equal(colourAt(3,4),'rgba(245,143,36,.75)');assert.equal(run('sceneEdits["3,4"]'),'rocks');
 assert.equal(run('proposalAt("3,4").template'),10);assert.equal(pending.length,pendingBeforeManual);
 assert.equal(run('payload().scene_edits["3,4"]'),'rocks');
 el('undo').onclick();assert.equal(run('sceneEdits["3,4"]'),undefined);assert.equal(colourAt(3,4),'rgba(255,36,36,.75)');
 // Unrelated changes and undo preserve a reviewed native choice even when
 // a fresh automatic choice would now prefer a different map.
 run('P.placements["3,3"]={kind:"rock",template:11,closed:["S"],allowed_exits:["N","E","W"]};S.catalog[11]={kind:"rock",closed:["S"]};layers.rocks.add("3,3");sceneEdits["3,3"]="rocks";capturePlan();planVersion=geomVersion;mode="water";');
 const reviewedTemplate=run('proposalAt("3,3").template');
 el('over').pointerdown({button:0,clientX:19,clientY:19,pointerId:23});windowHandlers.pointerup();
 el('undo').onclick();assert.equal(run('proposalAt("3,3").template'),reviewedTemplate);
 run('mode="wall";stamp(8,9);changed();');assert.equal(run('proposalAt("3,3").template'),reviewedTemplate);
 // Undoing a stroke after a review restores its earlier pending state,
 // never treats an unreviewed edit as if it belonged to the old plan.
 run('mode="coast";stamp(3,3);changed();mode="water";');
 el('over').pointerdown({button:0,clientX:19,clientY:19,pointerId:24});windowHandlers.pointerup();
 const temporarilyReviewed=JSON.parse(run('JSON.stringify(P)'));delete temporarilyReviewed.placements['3,3'];
 Object.assign(context,{temporarilyReviewed});run('showReviewedPlan(temporarilyReviewed,geomVersion);');
 el('undo').onclick();assert.equal(run('proposalAt("3,3").kind'),'coast');assert.notEqual(run('proposalAt("3,3").template'),reviewedTemplate);
 // A mismatched exact location can still be chosen; no automatic validation call.
 run('selected="2,1";');el('override').value='10';el('setOverride').onclick();
 assert.equal(run('layers.water.has("2,1")'),false);assert.equal(run('layers.rocks.has("2,1")'),true);
 assert.equal(run('proposalAt("2,1").template'),10);assert.equal(pending.length,pendingBeforeManual);
 // Editing one conflict must not hide the other conflict markers.
 run('P.issues=[{cell:"6,6",code:"manual_direction_conflict"},{cell:"7,7",code:"incompatible_neighbour"}];mode="wall";stamp(6,6);changed();');
 assert.ok(run('cache.ctx.strokes').some(v=>v[0]===42.4&&v[1]===42.4),'unrelated conflict remains painted');
 // The new wall-rim action is explicit, returns authored additions and can be undone.
 const wallRim=run("$('outlineWalls').onclick()");assert.equal(pending[0].path,'/outline-walls');
 const rimPlan=JSON.parse(JSON.stringify(fixture.plan));rimPlan.placements['5,5']={kind:'rock',template:10,closed:['N'],allowed_exits:['E','S','W']};
 await reply({additions:{'5,5':{kind:'rock',template:10}},plan:rimPlan});await wallRim;
 assert.equal(run('layers.rocks.has("5,5")'),true);assert.equal(run('overrides["5,5"]'),10);
 el('undo').onclick();assert.equal(run('layers.rocks.has("5,5")'),false);
 // Save is allowed before the optional transition review.
 const directSave=run("$('save').onclick()");assert.equal(pending[0].path,'/save');
 assert.equal(pending[0].body.scene_edits['2,1'],'rocks');await reply({revision:'manual-r4'});await directSave;
 assert.equal(run('dirty'),false);
 // Save returns a review of its geometry: remove a resolved marker only,
 // retaining the unrelated conflict on the map and in the list.
 run('P.issues=[{cell:"6,6",code:"manual_direction_conflict"},{cell:"7,7",code:"incompatible_neighbour"}];P.summary.unresolved=2;updateStats();render();mode="water";stamp(6,6);changed();');
 const correctedPlan=JSON.parse(run('JSON.stringify(P)'));correctedPlan.issues=[{cell:'7,7',code:'incompatible_neighbour'}];correctedPlan.summary.unresolved=1;
 const reviewedSave=run("$('save').onclick()");await reply({revision:'manual-r5',plan:correctedPlan});await reviewedSave;
 assert.equal(run('P.issues.length'),1);assert.equal(run('P.issues[0].cell'),'7,7');assert.equal(run('planVersion'),run('geomVersion'));
 assert.ok(el('issues').children.some(o=>o.value==='7,7'));assert.ok(!el('issues').children.some(o=>o.value==='6,6'));
 assert.ok(run('cache.ctx.strokes').some(v=>v[0]===42.4&&v[1]===42.4));
 assert.ok(!run('cache.ctx.strokes').some(v=>v[0]===36.4&&v[1]===36.4));
 // A save reply for an older geometry must not clear newer edit markers.
 const olderSave=run("$('save').onclick()");run('mode="water";stamp(8,8);changed();');
 const emptyPlan=JSON.parse(JSON.stringify(correctedPlan));emptyPlan.issues=[];emptyPlan.summary.unresolved=0;
 await reply({revision:'manual-r6',plan:emptyPlan});await olderSave;
 assert.equal(run('P.issues[0].cell'),'7,7');assert.equal(run('layers.water.has("8,8")'),true);assert.equal(run('dirty'),true);
 // A newer explicit review wins over an earlier save response for the same geometry.
 const savedEarlier=run("$('save').onclick()");const newerReview=run("$('calculate').onclick()");
 const newestPlan=JSON.parse(JSON.stringify(correctedPlan));newestPlan.issues=[{cell:'8,8',code:'manual_direction_conflict'}];
 const reviewRequest=pending.splice(1,1)[0];reviewRequest.resolve({ok:true,json:async()=>newestPlan});await newerReview;
 await reply({revision:'manual-r7',plan:correctedPlan});await savedEarlier;
 assert.equal(run('P.issues[0].cell'),'8,8');
 // Calculated depth never repaints authored colours, including after a save
 // or an explicit review. Unedited walls and independent conflicts stay intact.
 run('selected=null;layers={wall:new Set(["6,7"]),water:new Set(["7,7"]),rocks:new Set(["5,5"]),coast:new Set(["6,6"])};sceneEdits={"5,5":"rocks"};overrides={};P=JSON.parse(JSON.stringify(S.plan));P.effective_water=["7,7"];P.generated_walls=["5,5","6,7"];P.depth_cells=["5,5","6,6","6,7","8,6"];P.placements={"5,5":{kind:"rock",template:10},"6,6":{kind:"coast",template:18}};P.issues=[{cell:"5,5",code:"scene_inside_depth"},{cell:"7,8",code:"manual_direction_conflict"}];P.summary.unresolved=2;capturePlan();planVersion=geomVersion;render();');
 assert.equal(colourAt(5,5),'rgba(245,143,36,.75)');
 assert.equal(colourAt(6,6),'rgba(15,105,55,.8)');
 for(const colour of ['wall','water','rocks','coast','erase']){
  run('mode='+JSON.stringify(colour)+';if(stamp(5,5))changed();');
  const expected=colour==='erase'?undefined:run('COLORS['+JSON.stringify(colour)+']');
  assert.equal(colourAt(5,5),expected,'immediate manual colour: '+colour);
  const depthPlan=JSON.parse(run('JSON.stringify(P)'));
  if(colour==='rocks'||colour==='coast')depthPlan.placements['5,5']={kind:colour==='rocks'?'rock':'coast',template:colour==='rocks'?10:18};else delete depthPlan.placements['5,5'];
  const savingColour=run("$('save').onclick()");await reply({revision:'colour-'+colour,plan:depthPlan});await savingColour;
  assert.equal(colourAt(5,5),expected,'saved manual colour: '+colour);
  const reviewingColour=run("$('calculate').onclick()");await reply(depthPlan);await reviewingColour;
  assert.equal(colourAt(5,5),expected,'reviewed manual colour: '+colour);
  assert.equal(colourAt(6,6),'rgba(15,105,55,.8)','other depth scene stays green');
  assert.equal(colourAt(6,7),'rgba(255,36,36,.75)','other wall stays red');
  assert.equal(colourAt(7,7),'rgba(60,120,200,.55)','other water stays blue');
  assert.ok(run('cache.ctx.strokes').some(v=>v[0]===42.4&&v[1]===48.4),'unrelated warning retained');
 }
 // A blank calculated depth cell can be visually erased once without
 // deleting its neighbour's native collision or repeatedly dirtying the draft.
 assert.equal(colourAt(8,6),'rgba(255,36,36,.75)');
 assert.equal(run('mode="erase";stamp(8,6)'),true);run('changed();');
 assert.equal(colourAt(8,6),undefined);assert.equal(run('payload().scene_edits["8,6"]'),'erase');
 assert.equal(run('stamp(8,6)'),false);assert.equal(run('P.depth_cells.includes("8,6")'),true);
 // Among maps facing the same way, the brush prefers a native exit that
 // overlaps the already installed neighbour, instead of the lowest template id.
 run('S.catalog={10:{kind:"rock",closed:["N"],edges:{E:"3",W:"c",S:"f"}},11:{kind:"rock",closed:["N"],edges:{E:"c",W:"3",S:"f"}}};layers={wall:new Set(["4,3","5,3"]),water:new Set(),rocks:new Set(["5,4"]),coast:new Set()};sceneEdits={};overrides={};P.placements={"5,4":{kind:"rock",template:10}};P.generated_walls=[];P.depth_cells=[];capturePlan();planVersion=geomVersion;mode="rocks";stamp(4,4);changed();');
 assert.equal(run('proposalAt("4,4").template'),11);
 assert.equal(run('proposalAt("5,4").template'),10);
 // Changing neighbouring water refits an unpinned shore in the immediate
 // preview. The painted type and a deliberately pinned template stay unchanged.
 run('S.catalog={18:{kind:"coast",closed:["S"],edges:{N:"f",E:"f",W:"f"}},21:{kind:"coast",closed:["E","S"],edges:{N:"f",W:"f"}}};layers={wall:new Set(),water:new Set(["5,6"]),rocks:new Set(),coast:new Set(["5,5"])};sceneEdits={"5,5":"coast"};overrides={};P.placements={"5,5":{kind:"coast",template:18,closed:["S"],allowed_exits:["N","E","W"]}};P.generated_walls=[];P.depth_cells=[];capturePlan();planVersion=geomVersion;mode="water";stamp(6,5);changed();');
 assert.equal(run('proposalAt("5,5").template'),21);
 assert.equal(run('layers.coast.has("5,5")'),true);
 run('overrides["5,5"]=18;');assert.equal(run('proposalAt("5,5").template'),18);
 // Proposed coastal crocodiles use their own roster and draft positions.
 // The actual-game comparison and native inhabitant overrides stay independent.
 run('S.catalog={18:{kind:"coast",name:"native coast",closed:["S"],width:64,height:128}};layers={wall:new Set(),water:new Set(),rocks:new Set(),coast:new Set(["2,1"])};sceneEdits={"2,1":"coast"};overrides={};P.placements={"2,1":{kind:"coast",template:18,closed:["S"],allowed_exits:["N","E","W"]}};P.depth_cells=[];P.coastal_population={enabled:true,cells:{"2,1":{template:18,signature:"crocs-v1",city:"Вади-Хальфа",level:4,type_id:2418,positions:[65,130]}},excluded:{},summary:{locations:1,mobs:2}};S.mob_overrides={};S.coastal_mob_overrides={};selected="2,1";cellData={actual:{id:30,name:"old native",width:64,height:128,spawn_signature:"old-v1",spawns:[{index:0,cell:65,source_cell:65,type:123,name:"Native"}]}};capturePlan();planVersion=geomVersion;');
 el('viewActual').checked=false;run('renderCell();');
 assert.equal(run('localView().spawns.length'),2);assert.equal(run('localView().spawns[0].type'),2418);
 assert.ok(el('mobStatus').textContent.includes('4 ур.'));assert.equal(run('cellData.actual.spawns.length'),1);
 const coastalMove=run('moveMob(0,195)');assert.equal(pending[0].path,'/validate-coastal-mobs');
 await reply({'2,1':{template:18,signature:'crocs-v1',positions:[195,130]}});await coastalMove;
 assert.equal(run('S.coastal_mob_overrides["2,1"].positions[0]'),195);
 assert.equal(run('Object.keys(S.mob_overrides).length'),0);assert.equal(run('payload().coastal_mob_overrides["2,1"].positions[0]'),195);
 el('viewActual').checked=true;run('renderCell();');assert.equal(run('localView().spawns[0].type'),123);assert.equal(run('localView().spawns.length'),1);
 el('viewActual').checked=false;el('resetMobs').onclick();assert.equal(run('S.coastal_mob_overrides["2,1"]'),undefined);
 assert.equal(run('localView().spawns[0].cell'),65);assert.equal(run('cellData.actual.spawns[0].cell'),65);
 run('S.coastal_mob_overrides["2,1"]={template:18,signature:"old",positions:[195,130]}');assert.equal(run('localView().spawns[0].cell'),65);
 run('P.coastal_population.cells["2,1"].template=17');assert.equal(run('localView().spawns.length'),0);

 // Independent overlays preserve terrain, pins and each other, including undo.
 run('S.manual_editing=true;S.catalog={6:{kind:"rock",name:"corridor",closed:["E","W"],exits:["N","S"]},10:{kind:"rock",name:"old rock",closed:["N"]}};S.settlements={};P.placements={"5,5":{kind:"rock",template:10,closed:["N"],allowed_exits:[]}};P.depth_cells=[];layers={rocks:new Set(["5,5"]),wall:new Set(),water:new Set(),coast:new Set()};overlays={patrol:new Set(),tunnels:new Set()};sceneEdits={"5,5":"rocks"};overrides={"5,5":10};capturePlan();planVersion=geomVersion;mode="patrol";stamp(5,5);changed();mode="tunnels";stamp(5,5);changed();');
 assert.equal(run('layers.rocks.has("5,5")'),true);assert.equal(run('overrides["5,5"]'),10);
 assert.equal(run('overlays.patrol.has("5,5")&&overlays.tunnels.has("5,5")'),true);
 assert.equal(run('proposalAt("5,5").template'),6);assert.equal(run('proposalAt("5,5").global_map_exit'),false);
 assert.ok(run('cache.ctx.calls').some(v=>v[0]==='rgba(190,125,255,.8)'));
 assert.ok(run('cache.ctx.calls').some(v=>v[0]==='rgba(55,230,210,.85)'));
 el('colorPatrol').checked=false;el('colorPatrol').onchange();assert.ok(!run('cache.ctx.calls').some(v=>v[0]==='rgba(190,125,255,.8)'));
 assert.equal(run('payload().patrol[0]'),'5,5');el('colorPatrol').checked=true;
 el('eraseLayer').value='patrol';run('mode="erase";');el('over').pointerdown({button:0,clientX:31,clientY:31,pointerId:19});windowHandlers.pointerup();
 assert.equal(run('overlays.patrol.has("5,5")'),false);assert.equal(run('overlays.tunnels.has("5,5")'),true);assert.equal(run('layers.rocks.has("5,5")'),true);
 el('undo').onclick();assert.equal(run('overlays.patrol.has("5,5")'),true);assert.equal(run('overrides["5,5"]'),10);
 el('eraseLayer').value='tunnels';run('mode="erase";stamp(5,5);changed();');assert.equal(run('proposalAt("5,5").template'),10);
 assert.equal(run('layers.rocks.has("5,5")'),true);assert.equal(run('overlays.patrol.has("5,5")'),true);
 // The patrol is additive on an unmarked cell; actual comparison stays native.
 run('P.placements={};P.patrol_population={cells:{"5,5":{template:6,positions:[130,195],type_ids:[98,98],levels:[19,19],signature:"patrol-v1",occupied:[65]}},excluded:{},summary:{locations:1,mobs:2}};S.mob_overrides={};S.patrol_mob_overrides={};layers.rocks.clear();sceneEdits={};overrides={};selected="5,5";cellData={actual:{id:6,name:"native",width:64,height:128,spawn_signature:"native-v1",spawns:[{index:0,cell:65,source_cell:65,type:999,name:"Native NPC"}]}};capturePlan();planVersion=geomVersion;');
 el('viewActual').checked=false;run('renderCell();');assert.equal(run('localView().spawns.length'),3);assert.equal(run('localView().spawns[0].type'),999);
 const patrolMove=run('moveMob(1,256)');assert.equal(pending[0].path,'/validate-patrol-mobs');assert.deepEqual(pending[0].body.patrol,['5,5']);
 assert.equal(pending[0].body.patrol_mob_overrides['5,5'].positions.length,2);
 await reply({'5,5':{template:6,signature:'patrol-v1',positions:[256,195]}});await patrolMove;
 assert.equal(run('S.patrol_mob_overrides["5,5"].positions[0]'),256);assert.equal(run('Object.keys(S.mob_overrides).length'),0);
 el('viewActual').checked=true;run('renderCell();');assert.equal(run('localView().spawns.length'),1);assert.equal(run('localView().spawns[0].type'),999);
 // Comparing an installed snapshot must not reset or edit the draft's mobs.
 run('cellData.actual.installed_snapshot=true;');run('renderCell();');
 assert.equal(el('moveMob').disabled,true);assert.equal(el('resetMobs').disabled,true);
 const beforeActualReset=run('JSON.stringify(payload())'),beforeActualVersion=run('editVersion');
 el('resetMobs').onclick();assert.equal(run('JSON.stringify(payload())'),beforeActualReset);assert.equal(run('editVersion'),beforeActualVersion);
 await assert.rejects(run('moveMob(0,66)'),/установленная копия/i);
 assert.ok(el('mobStatus').textContent.includes('только для сравнения'));
 run('delete cellData.actual.installed_snapshot;');
 el('viewActual').checked=false;el('mobChoice').value='1';el('resetMobs').onclick();assert.equal(run('S.patrol_mob_overrides["5,5"]'),undefined);
 assert.equal(run('cellData.actual.spawns[0].cell'),65);
 const nativeAlongside=run('moveMob(0,66)');assert.equal(pending[0].path,'/validate-mobs');assert.deepEqual(pending[0].body.mob_overrides['5,5'].positions,[66]);
 await reply({'5,5':{location_id:6,spawn_signature:'native-v1',positions:[66]}});await nativeAlongside;
 assert.equal(run('S.mob_overrides["5,5"].positions[0]'),66);assert.equal(run('localView().spawns.length'),1,'patrol preview waits for its updated occupancy signature');
 // Explicit physical repairs remain undoable and cannot replace newer strokes.
 const beforeRepair=run('JSON.stringify(payload())'),repairDraft=JSON.parse(beforeRepair);
 repairDraft.blocked.push('8,8');repairDraft.scene_edits['8,8']='wall';
 const repairPlan=JSON.parse(run('JSON.stringify(P)'));repairPlan.issues=[];repairPlan.summary.unresolved=0;
 const repairClick=el('repairBorders').onclick();assert.equal(pending[0].path,'/repair-boundaries');
 await reply({draft:repairDraft,plan:repairPlan,report:{before:3}});await repairClick;
 assert.equal(run('layers.wall.has("8,8")'),true);assert.equal(run('dirty'),true);
 el('undo').onclick();assert.equal(run('layers.wall.has("8,8")'),false);
 const staleRepair=el('repairBorders').onclick();run('editVersion++');
 await reply({draft:repairDraft,plan:repairPlan,report:{before:3}});await staleRepair;
 assert.equal(run('layers.wall.has("8,8")'),false);
 console.log('PASS: visibility, colour blending, opacity, save race, point overrides and stale calculations');
})().catch(error=>{console.error(error);process.exitCode=1;});
"""

class PreviewBrowser(unittest.TestCase):
    def test_real_ui_preserves_data_and_rejects_stale_async_results(self):
        node=shutil.which('node')
        fallback=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'nodejs/node.exe'
        if not node and fallback.is_file():node=str(fallback)
        if not node:self.skipTest('Node.js is needed for the isolated browser-script check')
        script=PAGE.split('<script>',1)[1].split('</script>',1)[0]
        with tempfile.TemporaryDirectory(prefix='boundary-ui-') as folder:
            harness=Path(folder)/'harness.cjs';harness.write_text(HARNESS,encoding='utf-8')
            result=subprocess.run([node,str(harness)],input=script,encoding='utf-8',capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        self.assertIn('PASS:',result.stdout)

if __name__=='__main__':run_cases(PreviewBrowser)
