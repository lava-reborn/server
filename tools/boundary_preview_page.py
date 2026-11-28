"""UI for the isolated boundary editor; no game installation controls."""
PAGE = r"""<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Lava — предпросмотр границ</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#171813;color:#eee9da;font:14px/1.4 system-ui,sans-serif;height:100vh;display:flex;flex-direction:column}button,input,select{font:inherit}button{border:1px solid #79765b;border-radius:4px;background:#414735;color:#fff;padding:5px 9px;cursor:pointer}button:disabled{opacity:.45;cursor:wait}button[aria-pressed=true]{outline:2px solid #ffe5a3}input,select{background:#262b23;color:#fff;border:1px solid #73765e;padding:4px;border-radius:3px}label{display:inline-flex;align-items:center;gap:5px}input[type=range]{width:100px}header{padding:9px 12px;background:#242b20;border-bottom:1px solid #626b4c}header strong{color:#e9dbad}.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:6px 0}#water{background:#285e99}#wall{background:#b31e1e}#rocks{background:#ae5e17}#coast{background:#0f6937}#main{display:flex;min-height:0;flex:1}#wrap{flex:1;overflow:auto;position:relative;background:#12150f}#space{position:relative}#stage{position:absolute;transform-origin:0 0}#map{display:block;user-select:none}canvas{position:absolute;inset:0;touch-action:none;image-rendering:pixelated}aside{width:420px;min-width:280px;max-width:80vw;flex-shrink:0;padding:12px;background:#22281f;overflow:auto;border-left:1px solid #596247}aside p{margin:7px 0}aside input[type=text]{width:122px}aside select{width:100%}#local{display:block;width:auto;max-width:100%;height:auto;max-height:none;object-fit:contain;background:#bca67e;border:1px solid #717c56;cursor:crosshair}#art{width:100%;display:none}#neighbours{display:grid;grid-template-columns:repeat(3,1fr);gap:3px;margin:8px 0}.tile{border:1px solid #6e765b;font-size:10px;min-height:64px;cursor:pointer;background:#31392b;text-align:center}.tile img{display:block;width:100%}.tile span{display:block;padding:2px}#details{white-space:pre-line}#status{color:#e8d796;min-height:22px}#counts{font-size:13px;color:#c1d0aa}#source{font-size:12px;color:#b9c1ae}.warn{color:#ffc27d}.hint{font-size:12px;color:#b9c1ae}hr{border:0;border-top:1px solid #586246;margin:12px 0}#routeStart,#routeEnd{width:130px}#localStart,#localEnd{width:75px}@media(max-width:620px){#main{flex-direction:column}aside{width:100%;max-height:38vh;border-left:0;border-top:1px solid #596247}#wrap{min-height:230px}header{padding:7px}.toolbar{gap:6px}}
#resizeAside{width:8px;flex-shrink:0;cursor:col-resize;background:#596247;touch-action:none}#resizeAside:hover{background:#d6c27b}#art{max-height:70vh;object-fit:contain}#local{width:100%;height:480px}@media(max-width:620px){#resizeAside{display:none}aside{min-width:0;max-width:none;width:100%!important}}
#localFrame{position:relative}#art{position:absolute;inset:0;width:100%;height:100%;max-height:none;object-fit:contain}#local{position:relative;background:transparent}#mobOverlay{position:absolute;inset:0;width:100%;height:100%;touch-action:none;pointer-events:none}#mobOverlay [data-mob]{pointer-events:all;cursor:grab}#mobX,#mobY{width:65px}
</style>
<header><strong>Границы · новый редактор</strong> <span class="hint">Сохранение черновика · установки в игру нет</span>
<div id="source">Загрузка снимка…</div>
<div class="toolbar">
<button id="inspect" aria-pressed="true">Осмотр</button><button id="water" aria-pressed="false">Вода</button><button id="wall" aria-pressed="false">Стена</button><button id="rocks" aria-pressed="false">Скалы</button><button id="coast" aria-pressed="false">Побережье</button><button id="patrol" aria-pressed="false" style="background:#76509c">Патруль Магриба</button><button id="tunnels" aria-pressed="false" style="background:#176963">Тоннель N↕S</button><button id="erase" aria-pressed="false">Стереть</button><label>Стирать <select id="eraseLayer" aria-label="Слой для стирания"><option value="terrain">Рельеф</option><option value="patrol">Патруль</option><option value="tunnels">Тоннель</option><option value="all">Все слои</option></select></label><button id="undo">Отменить штрих</button>
<label>Кисть <input id="size" type="range" min="1" max="15" step="2" value="1"><output id="brushValue">1</output></label>
<label>Непрозрачность <input id="opacity" type="range" min="0" max="100" value="70"><output id="alpha">70%</output></label>
</div><div class="toolbar">
<label><input id="manual" type="checkbox" checked>Ручной слой</label><label><input id="showauto" type="checkbox" checked>Показать назначения</label><label><input id="showplaces" type="checkbox" checked>Особые локации</label>
<button id="outlineWalls">Создать пограничные локации у стен</button><button id="repairBorders">Исправить стыки и обводку</button><button id="calculate">Обновить переходы и замечания</button><button id="save">Сохранить черновик</button>
<label>Масштаб <input id="zoom" type="range" min="25" max="400" value="100"><output id="zoomValue">100%</output></label>
</div><div class="toolbar" aria-label="Видимость цветов">
<span class="hint">Цвета:</span><label><input id="colorWater" type="checkbox" checked>Вода</label><label><input id="colorWall" type="checkbox" checked>Стены</label><label><input id="colorRocks" type="checkbox" checked>Скалы</label><label><input id="colorCoast" type="checkbox" checked>Побережья</label><label><input id="colorIssues" type="checkbox" checked>Спорные места</label>
<label><input id="colorPatrol" type="checkbox" checked>Патруль Магриба</label><label><input id="colorTunnels" type="checkbox" checked>Тоннели</label>
</div><div id="counts"></div><div id="accessCounts" class="warn"></div><div id="status" role="status" aria-live="polite">Загрузка…</div></header>
<div id="main"><div id="wrap"><div id="space"><div id="stage"><img id="map" draggable="false" alt="Актуальная глобальная карта игры"><canvas id="over"></canvas></div></div></div>
<div id="resizeAside" role="separator" aria-label="Ширина бокового меню" aria-orientation="vertical" tabindex="0"></div><aside id="sidebar"><hr><strong>Родная локальная геометрия</strong><p id="templateName" class="hint">Выбери назначенную локацию.</p><label>Размер геометрии <input id="previewSize" type="range" min="240" max="1400" value="480"><output id="previewSizeValue">480 px</output></label><p><label><input id="showArtwork" type="checkbox" checked>Изображение</label> <label><input id="showGeometry" type="checkbox" checked>Геометрия</label> <label><input id="showHexes" type="checkbox" checked>Гексы</label> <label><input id="viewActual" type="checkbox">Текущая локация из игры</label></p><div id="localFrame"><img id="art" alt="Изображение текущей или предложенной локации"><img id="local" alt="Схема препятствий, входов и выходов" hidden><svg id="mobOverlay" aria-label="Мобы на геометрии локации"></svg></div><p id="cellActual" class="hint">Читаю текущую локацию…</p><label><input id="showMobs" type="checkbox" checked>Мобы</label> <label><input id="moveMobs" type="checkbox">Двигать мобов</label><p><select id="mobChoice" aria-label="Выбранный моб"></select></p><label>X <input id="mobX" type="number" min="0" value="0"></label> <label>Y <input id="mobY" type="number" min="0" value="0"></label><button id="moveMob">Передвинуть</button><button id="resetMobs">Сбросить позиции</button><p id="mobStatus" class="hint">Позиции сохраняются только в черновик.</p><p id="artStatus" class="hint"></p>
<p class="hint">На схеме: тёмные клетки — препятствия, зелёные — входы, синие — выходы. Нажатия выбирают начало и конец локального пути.</p>
<label>От <input id="localStart" type="number" min="0" value="0"></label> <label>До <input id="localEnd" type="number" min="0" value="1"></label><button id="testLocal">Проверить гексы</button><p id="localResult" class="hint"></p>
<hr>
<label>X <input id="gx" type="text" value="5997" size="5"></label> <label>Y <input id="gy" type="text" value="1679" size="5"></label><button id="goto">Показать клетку</button>
<p id="details">Выбери клетку в режиме «Осмотр».</p>
<select id="override" aria-label="Шаблон выбранной клетки"><option value="auto">Автоподбор</option><option value="off">Убрать назначение</option></select><p><button id="setOverride">Задать для клетки</button></p><p id="catalogUsage" class="hint"></p>
<select id="issues" aria-label="Спорные клетки"><option value="">Спорные клетки</option></select>
<p class="hint">Фиолетовые отметки — патруль Магриба 19 ур., бирюзовые боковые полосы — тоннель N/S без выхода на глобал. Оба слоя независимы от рельефа и могут сочетаться. Чтобы убрать только метку, выбери её в поле «Стирать». Для спавнов и переходов нажми «Обновить переходы и замечания» или сохрани черновик. Тёмно-зелёный — побережье, оранжевый — скальная карта, красный — стена, синий — вода. Кисть сразу меняет тип выбранной клетки; соседние клетки автоматически не перерисовываются. Цвет ручной метки сохраняется после обновления и записи. Закрытая глубина не перекрашивает её: конфликт показывается отдельным контуром. Для скал и побережий подбирается родной вариант по соседней глубине и совместимым выходам соседей. Подбор проверяет соседние карты совместно по родным выходам, связной суше и закрытым сторонам. Исправные стыки сохраняются; совместимые варианты скал чередуются. Скальные проходы 5/6 используются только при глубине с двух соответствующих сторон. Цвета и границы автоматически не перерисовываются. Явно выбранная карта сохраняется. Отдельная кнопка «Исправить стыки и обводку» может заменить ошибочные шаблоны и добавить родные скальные или прибрежные карты перед глубиной; результат можно отменить до сохранения. «Обновить переходы и замечания» показывает разрешённые стыки и спорные места. Замечания не блокируют сохранение и не заменяют назначение стеной. Сохранение обновляет замечания по сохранённым правкам. Белая рамка — выбранная клетка; жёлтый и розовый контуры — замечания. «Стереть» и отмена штриха работают со всеми цветами. При удалении автоматического берега вода под ним сохраняется. Средняя кнопка мыши перемещает карту; Ctrl + колесо меняет масштаб.</p>
<details id="neighbourSection"><summary>Соседние карты · 3×3</summary><div id="neighbours"></div></details><hr><strong>Проверка глобального пути</strong>
<p><label>От <input id="routeStart" type="text" value="5997,1679"></label></p><p><label>До <input id="routeEnd" type="text" value="5998,1679"></label></p><button id="testRoute">Проверить путь</button><p id="routeResult" class="hint">Два слоя: доступность глобальной клетки и стороны перехода, затем родные препятствия и выходы локации.</p>
<p class="hint">Два слоя проходимости: глобальная клетка и родная геометрия локальной карты. Скальная или прибрежная карта образует доступный край; отмеченная глубина за ним остаётся непроходимой. Выход действует только через доступные гексы и совместимый встречный выход соседней карты. Стена и вода проходов не получают. Эдем и Нубия сохраняют изоляцию. Тёмные пиксели фонового изображения автоматически не определяют препятствия.</p>
</aside></div>
<script>
let S=null,P=null,mode='inspect',brush=1,zoom=1,painting=false,last=null,dirty=false,editVersion=0,geomVersion=0,planVersion=0,reviewEpoch=0,selected=null,selectedTemplate=null,localPick=0,routePath=[],pan=null,strokeCells=new Set();
let layers={wall:new Set(),water:new Set(),rocks:new Set(),coast:new Set()},overlays={patrol:new Set(),tunnels:new Set()},overrides={},sceneEdits={},planScenes={},undo=[],planMarks=new Map(),planOverrides={},planWalls=new Set();
function currentMarksAt(key){return ['coast','rocks','water','wall'].find(name=>layers[name].has(key));}
function currentMarks(){const out=new Map();for(const name of ['wall','water','rocks','coast'])for(const key of layers[name])out.set(key,name);return out;}
function capturePlan(){planMarks=currentMarks();planOverrides={...overrides};planScenes={...sceneEdits};planWalls=new Set(P?.generated_walls||[]);}
function editSnapshot(){return {layers:Object.fromEntries(Object.entries(layers).map(([k,v])=>[k,new Set(v)])),overlays:Object.fromEntries(Object.entries(overlays).map(([k,v])=>[k,new Set(v)])),overrides:{...overrides},scenes:{...sceneEdits},plan:P,marks:new Map(planMarks),reviewedOverrides:{...planOverrides},reviewedScenes:{...planScenes}};}
const $=id=>document.getElementById(id),ctx=$('over').getContext('2d'),cache=document.createElement('canvas'),cc=cache.getContext('2d');
const COLORS={wall:'rgba(255,36,36,.75)',water:'rgba(60,120,200,.55)',rocks:'rgba(245,143,36,.75)',coast:'rgba(15,105,55,.8)'};
const MODES=['inspect','water','wall','rocks','coast','patrol','tunnels','erase'];
const COLOR_SWITCH={water:'colorWater',wall:'colorWall',rocks:'colorRocks',coast:'colorCoast'};
const reasons={boundary_missing_scene:'Перед стеной или водой нет локации с родным препятствием',boundary_no_native_template:'Нет родного шаблона для этих закрытых сторон',tunnel_terrain_conflict:'Тоннель пересекает воду, стену или побережье',tunnel_existing_location:'Тоннель не заменяет существующее место с обитателями или квестом',tunnel_template_unavailable:'Нет родного тоннеля с выходами N/S',patrol_terrain_conflict:'Патрулю нужна скальная карта или непомеченная суша',patrol_isolated_region:'Патруль не добавлен в изолированную область',patrol_blocked:'Патрульная клетка закрыта глубиной или границей',patrol_peaceful_location:'Исходная карта не поддерживает бой — обитатели сохранены',patrol_no_safe_area:'Недостаточно безопасного места для патруля',existing_location_overlap:'Ручное назначение пересекает существующую локацию',manual_direction_conflict:'Стороны выбранной карты не совпадают с соседней глубиной',scene_inside_depth:'Локация попала в закрытую глубину за границей',manual_depth_conflict:'Метка стёрта, но клетка остаётся за закрытой стороной соседней карты',depth_hits_existing:'Закрытая сторона направлена в существующую локацию — нужен другой стык',missing_depth_backing:'За закрытой стороной нет отмеченной глубины или стены',manual_coast_no_template:'Для ручного побережья нет подходящего берега: проверь соседнюю воду и шаблон',isolated_boundary:'Одиночный участок закрыт стеной',isolated_coast:'У берега нет подходящего соседа — участок закрыт',coast_channel_preserved:'Узкий край оставлен непроходимым: сохраняем русло',backing_wall_conflict:'За скалами нет безопасного места для стены — клетка закрыта',assignment_suppressed:'Назначение убрано — клетка закрыта до проверки',protected_mark_conflict:'Разметка пересекает особую локацию',protected_location:'Существующая локация сохранена',ambiguous_rock_direction:'Неясно направление скал',no_matching_template:'Нет подходящего шаблона',override_conflict:'Ручной шаблон не подходит направлению',override_outside_boundary:'Назначение вне границы',incompatible_neighbour:'Несовместимый стык с соседом',component_needs_manual_review:'Участок требует ручного выбора',no_safe_return:'Нет безопасного выхода на сушу'};
function payload(){return {mountain_complexes:S?.mountain_complexes||{},mountain_trails:!!S?.mountain_trails,physical_boundary_audit:!!S?.physical_boundary_audit,patrol:[...overlays.patrol],tunnels:[...overlays.tunnels],patrol_mob_overrides:{...(S?.patrol_mob_overrides||{})},water:[...layers.water],rocks:[...layers.rocks],coast:[...layers.coast],blocked:[...layers.wall,...layers.water,...layers.rocks],passable:[],overrides:{...overrides},mob_overrides:{...(S?.mob_overrides||{})},coastal_mob_overrides:{...(S?.coastal_mob_overrides||{})},scene_edits:{...sceneEdits},eden_inset:S.eden_inset||0,opacity:+$('opacity').value,revision:S.revision};}
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error||'Ошибка запроса');return data;}
function message(value){$('status').textContent=value;}
function accessReport(){return S&&P&&geomVersion===planVersion&&S.accessibility&&S.accessibility.geometry===P.input_fingerprint?S.accessibility:null;}
const accessReasons={blocked_by_draft:'Черновик закрыл клетку',approach_blocked_by_draft:'Перекрыты подходы',disconnected_by_draft:'Отрезана от общей области',not_globally_accessible_before:'Была недоступна на глобале раньше',accessible:'Доступ сохранён'};
function changed(){dirty=true;editVersion++;geomVersion++;routePath=[];$('accessCounts').textContent=S?.manual_editing?'Ручной режим: замечания не блокируют сохранение.':'Границы изменены — доступность старых точек нужно перепроверить';message(S?.manual_editing?'Ручное назначение изменено. Можно сохранить; переходы и замечания обновляются отдельной кнопкой.':'Разметка копии изменена — авторазметку нужно пересчитать.');render();}
function xy(k){return k.split(',').map(Number);}
function inBounds(x,y){return S&&x>=S.bounds[0]&&y>=S.bounds[1]&&x<=S.bounds[2]&&y<=S.bounds[3];}
function rect(k,p=6){const[x,y]=xy(k);return [(x-S.bounds[0])*p,(y-S.bounds[1])*p,p,p];}
function render(){
 if(!S)return;cc.clearRect(0,0,cache.width,cache.height);cc.globalAlpha=+$('opacity').value/100;
 const current=currentMarks(),marks=$('manual').checked?new Map(current):new Map();
 if($('showauto').checked&&P){
  for(const [k,type] of planMarks)if(type==='water')marks.delete(k);
  for(const k of P.preserved_land||[])marks.delete(k);
  const preserved=new Set(P.preserved_land||[]);
  for(const [k,type] of planMarks)if(type==='wall'&&!preserved.has(k))marks.set(k,'wall');
  for(const k of P.effective_water||layers.water)marks.set(k,'water');
  for(const k of P.generated_walls||[])marks.set(k,'wall');
  for(const[k,row]of Object.entries(P.placements))marks.set(k,row.kind==='coast'?'coast':'rocks');
  for(const k of P.depth_cells||[])if(!layers.water.has(k)&&!(S.manual_editing&&P.placements[k]))marks.set(k,'wall');
  // Authored colours describe the user's choice, not calculated passability.
  // Keep them after review/save; depth conflicts have their own outline.
  if(S.manual_editing)for(const k of Object.keys(sceneEdits)){marks.delete(k);if(current.has(k))marks.set(k,current.get(k));}
  if(geomVersion!==planVersion)for(const k of new Set([...planMarks.keys(),...current.keys(),...Object.keys(overrides),...Object.keys(planOverrides),...Object.keys(sceneEdits),...Object.keys(planScenes)])){if(planMarks.get(k)!==current.get(k)||overrides[k]!==planOverrides[k]||sceneEdits[k]!==planScenes[k]){marks.delete(k);if(current.has(k))marks.set(k,current.get(k));}}
 }
 for(const[k,name]of marks){if(!$(COLOR_SWITCH[name]).checked)continue;cc.fillStyle=COLORS[name];cc.fillRect(...rect(k));}
 for(const k of overlays.patrol)if($('colorPatrol').checked){const[x,y,w,h]=rect(k);cc.fillStyle='rgba(190,125,255,.8)';cc.fillRect(x+.5,y+.5,w-1,1.5);cc.fillRect(x+2,y+2,2,2);}
 for(const k of overlays.tunnels)if($('colorTunnels').checked){const[x,y,w,h]=rect(k);cc.fillStyle='rgba(55,230,210,.85)';cc.fillRect(x+.3,y+.3,1.3,h-.6);cc.fillRect(x+w-1.6,y+.3,1.3,h-.6);}
 cc.globalAlpha=1;
 if($('showauto').checked&&$('colorIssues').checked&&P&&(geomVersion===planVersion||S.manual_editing)){const extra=accessReport()?.regressions.map(r=>({cell:r.cell,code:'protected_access_conflict'}))||[];for(const row of [...P.issues,...extra]){if(row.code==='protected_location')continue;const critical=['protected_mark_conflict','protected_access_conflict','existing_location_overlap','depth_hits_existing','scene_inside_depth','manual_depth_conflict'].includes(row.code);cc.strokeStyle=critical?'#ff45d1':'#ffce5b';cc.lineWidth=critical?1.8:.8;const[x,y,w,h]=rect(row.cell);cc.strokeRect(x+.4,y+.4,w-.8,h-.8);}}
 if($('showplaces').checked){cc.fillStyle='rgba(255,224,60,.65)';for(const k of Object.keys(S.settlements)){const[x,y]=rect(k);cc.fillRect(x+1,y+1,4,4);}}
 draw();
}
function draw(){ctx.clearRect(0,0,$('over').width,$('over').height);ctx.drawImage(cache,0,0);if(routePath.length){ctx.strokeStyle='#fff';ctx.lineWidth=2;ctx.beginPath();routePath.forEach((k,i)=>{const[x,y]=rect(k);if(i)ctx.lineTo(x+3,y+3);else ctx.moveTo(x+3,y+3);});ctx.stroke();}if(selected){const[x,y]=rect(selected);ctx.strokeStyle='#fff';ctx.lineWidth=1.5;ctx.strokeRect(x-.5,y-.5,7,7);}}
function showReviewedPlan(plan,version){P=plan;planVersion=version;reviewEpoch++;capturePlan();updateStats();render();if(selected)inspect(selected);}
function updateStats(){if(!P)return;const usage={};for(const row of Object.values(P.placements||{}))usage[row.template]=(usage[row.template]||0)+1;$('catalogUsage').textContent='Шаблоны в схеме: '+Object.entries(usage).sort((a,b)=>+a[0]-b[0]).map(([id,count])=>id+' × '+count).join(', ')+'. Не включены: берега 38/39 (вода с двух сторон), 54–57 (полуострова).';const s=P.summary;$('counts').textContent=`Русло: ${s.water} · Заменено краёв воды: ${s.replaced_water||0} · Ручные стены: ${s.walls} · Побережья: ${s.coast} · Скальные локации: ${s.rock_locations} · Сухие переходы: ${s.dry_connectors||0} · Обводка стен: ${s.wall_outline||0} · Нерешённые: ${s.unresolved} · Закрытая глубина: ${s.added_walls}`;if(P.coastal_population?.enabled)$('counts').textContent+=' · Крокодилы: '+P.coastal_population.summary.mobs+' на '+P.coastal_population.summary.locations+' берегах';if(P.patrol_population)$('counts').textContent+=' · Патруль: '+P.patrol_population.summary.mobs+' на '+P.patrol_population.summary.locations+' клетках';$('counts').textContent+=' · Тоннели: '+Object.keys(P.tunnels||{}).length;const list=$('issues');list.hidden=s.unresolved===0;list.replaceChildren(new Option('Спорные клетки ('+s.unresolved+')',''));for(const row of P.issues){const text=row.cell+' — '+(reasons[row.code]||row.code)+(row.existing!==undefined?' · локация '+row.existing:'')+(row.neighbour?' → '+row.neighbour:'');list.add(new Option(text,row.cell));}const a=accessReport();$('accessCounts').textContent=S.manual_editing?'Ручной режим: замечания не блокируют сохранение.':a?'Старые точки: доступ сохранён у '+a.summary.accessible+' из '+a.baseline_accessible+' · проблем с доступом: '+a.regressions.length:'Доступность старых точек после изменения границ нужно перепроверить';if(a)for(const row of a.regressions)if(!P.issues.some(i=>i.cell===row.cell&&i.code==='protected_mark_conflict'))list.add(new Option(row.cell+' — '+row.title+' · '+accessReasons[row.status],row.cell));}
function setZoom(value){zoom=Math.max(.25,Math.min(4,value));$('zoom').value=Math.round(zoom*100);$('zoomValue').textContent=Math.round(zoom*100)+'%';$('stage').style.transform='scale('+zoom+')';$('space').style.width=cache.width*zoom+'px';$('space').style.height=cache.height*zoom+'px';}
function go(k){const[x,y]=xy(k);if(!inBounds(x,y)){message('Координаты вне карты');return;}$('gx').value=x;$('gy').value=y;$('wrap').scrollLeft=Math.max(0,(x-S.bounds[0])*6*zoom-$('wrap').clientWidth/2);$('wrap').scrollTop=Math.max(0,(y-S.bounds[1])*6*zoom-$('wrap').clientHeight/2);inspect(k);}

function proposalAt(key){
 let legacy=P?.placements[key]||null;
 if(legacy?.tunnel&&!overlays.tunnels.has(key))legacy=legacy.tunnel_underlay||null;
 if(overlays.tunnels.has(key)&&S.catalog[6]&&!layers.water.has(key)&&!layers.wall.has(key)&&!layers.coast.has(key)&&legacy?.kind!=='coast'&&S.settlements[key]===undefined){const pr=S.catalog[6];if(legacy?.tunnel)return legacy;return {template:6,kind:'rock',closed:pr.closed,native_exits:pr.exits||[],allowed_exits:[],tunnel:true,tunnel_underlay:legacy,global_map_exit:false,global_map_entry:false,transitions_pending:true,manual:true};}
 if(!S?.manual_editing)return geomVersion===planVersion?legacy:null;
 if(overrides[key]===null)return null;
 const edit=sceneEdits[key],exact=overrides[key];
 const unchanged=planMarks.get(key)===currentMarksAt(key)&&exact===planOverrides[key]&&edit===planScenes[key];
 const neighbourChanged=[[0,-1],[1,0],[0,1],[-1,0]].some(([dx,dy])=>{const[x,y]=xy(key),k=(x+dx)+','+(y+dy);return currentMarksAt(k)!==planMarks.get(k)||overrides[k]!==planOverrides[k]||sceneEdits[k]!==planScenes[k];});
 if(legacy&&unchanged&&(exact===undefined||legacy.template===exact)&&(geomVersion===planVersion||!neighbourChanged||exact!==undefined))return geomVersion===planVersion?legacy:{...legacy,transitions_pending:true};
 if(!edit&&exact===undefined)return legacy?{...legacy,transitions_pending:geomVersion!==planVersion}:null;
 if(exact===undefined&&!['rocks','coast'].includes(edit))return null;
 const kind=exact!==undefined?S.catalog[exact]?.kind:edit==='rocks'?'rock':'coast';
 const [x,y]=xy(key),hasScene=k=>overrides[k]!==null&&(['rocks','coast'].includes(sceneEdits[k])||!sceneEdits[k]&&P?.placements[k]);
 const back=(a,b)=>{const k=a+','+b;if(!inBounds(a,b))return true;if(hasScene(k))return false;return kind==='coast'?layers.water.has(k):layers.water.has(k)||layers.wall.has(k)||layers.rocks.has(k)||planWalls.has(k)&&!sceneEdits[k];};
 const step={N:[0,-1],E:[1,0],S:[0,1],W:[-1,0]},wanted=Object.keys(step).filter(side=>back(x+step[side][0],y+step[side][1]));
 const choices=Object.keys(S.catalog).map(Number).filter(id=>S.catalog[id].kind===kind&&![30,51].includes(id));
 const score=id=>{const closed=S.catalog[id].closed;return wanted.filter(s=>!closed.includes(s)).length+closed.filter(s=>!wanted.includes(s)).length;};
 const opposite={N:'S',E:'W',S:'N',W:'E'},bitCount=n=>{let count=0;for(;n;n&=n-1n)count++;return count;};
 const neighbours=Object.entries(step).flatMap(([side,[dx,dy]])=>{const k=(x+dx)+','+(y+dy);if(back(x+dx,y+dy))return [];const previous=P?.placements[k],id=overrides[k]??(sceneEdits[k]===planScenes[k]&&currentMarksAt(k)===planMarks.get(k)?previous?.template:undefined);return id!==undefined&&overrides[k]!==null&&S.catalog[id]?.edges?[[side,S.catalog[id]]]:[];});
 const seamScore=id=>{let conflicts=0,cost=0;const edges=S.catalog[id].edges;if(!edges)return [0,0];for(const[side,other]of neighbours){const a=BigInt('0x'+(edges[side]||'0')),b=BigInt('0x'+(other.edges[opposite[side]]||'0'));if(Boolean(a)!==Boolean(b)||(a&&!(a&b)))conflicts++;else cost+=bitCount(a^b)/Math.max(1,bitCount(a|b));}return [conflicts,cost];};
 const seams=new Map(choices.map(id=>[id,seamScore(id)]));
 const variantRank=id=>{let value=2166136261;for(const c of key+':'+id)value=Math.imul(value^c.charCodeAt(0),16777619)>>>0;return value;};
 choices.sort((a,b)=>score(a)-score(b)||seams.get(a)[0]-seams.get(b)[0]||S.catalog[a].closed.filter(s=>!wanted.includes(s)).length-S.catalog[b].closed.filter(s=>!wanted.includes(s)).length||seams.get(a)[1]-seams.get(b)[1]||variantRank(a)-variantRank(b));
 const id=exact??choices[0];if(id===undefined)return null;
 if(legacy&&unchanged&&exact===undefined&&(score(id)!==0||seams.get(id)[0]!==0))return {...legacy,transitions_pending:true};
 const pr=S.catalog[id];
 return {template:id,kind:pr.kind,closed:pr.closed,native_exits:pr.exits||[],allowed_exits:[],transitions_pending:true,manual:true};
}
function inspect(k){selected=k;const [cellX,cellY]=xy(k);$('gx').value=cellX;$('gy').value=cellY;draw();const row=proposalAt(k);const labels=[];for(const name of Object.keys(layers))if(layers[name].has(k))labels.push({wall:'исходная ручная стена',water:'исходная водная разметка',rocks:'скальная область',coast:'ручное побережье'}[name]);const issues=P?P.issues.filter(r=>r.cell===k):[];
 let text=k+'\n'+labels.join(', ');if(overlays.patrol.has(k))text+='\nПатруль Магриба · 19 ур. · отдельный слой';if(overlays.tunnels.has(k))text+='\nТоннель N↕S: только север/юг, без прямого входа и выхода через глобальную карту';if(P&&geomVersion===planVersion&&(P.cleared_land||[]).includes(k))text+='\nМетка стёрта: автоматические стены и локации здесь отключены';if(P&&geomVersion===planVersion&&(P.preserved_land||[]).includes(k))text+='\nСохранена существующая локация / подход: ручная граница здесь не закрывает проход';if(P&&geomVersion===planVersion&&(P.generated_walls||[]).includes(k))text+='\nАвторазметка: непроходимая стена без локации';if(P&&geomVersion===planVersion&&(P.effective_water||[]).includes(k)&&!(P.preserved_land||[]).includes(k))text+='\nАвторазметка: непроходимое русло, вход в локацию закрыт';for(const[name,cells]of Object.entries(P?.isolated_regions||{}))if(cells.includes(k))text+='\nИзолированная область: '+(name==='eden'?'Эдем':'Нубия');if(S.settlements[k]!==undefined)text+='\nОсобая локация '+S.settlements[k];if(S.manual_editing&&(P?.depth_cells||[]).includes(k))text+='\nВторой слой: клетка за закрытой стороной соседней карты; цвет метки не открывает проход';if(row){if(row.mountain_trail||row.mountain_portal){text+='\nГорные тропы · '+row.trail_family+' · исходная локация '+row.source_location+' сохранена';for(const door of row.door_designs||[])text+='\nПереход '+door.source_side+' → '+(door.target_loc_id??'цель не задана в исходных данных')+' · сторона '+door.side;}if(row.role==='dry_connector')text+='\nСухой соединительный участок; используются только родные ресурсы карты';if(row.spawn_policy==='none')text+='\nЭдем: без крокодилов и выхода во внешний мир';if(row.replaces==='water')text+='\nКрай воды заменён побережьем';text+='\nШаблон '+row.template+' · '+(row.kind==='coast'?'побережье':'скалы')+'\nЗакрыто: '+row.closed.join(', ')+'\nПереходы: '+(row.transitions_pending?'обнови переходы отдельной кнопкой':row.allowed_exits.join(', ')||'нет')+'\n'+(row.manual?'Ручное назначение':'Автоподбор');}if(geomVersion!==planVersion)text+=S.manual_editing?'\nПереходы и замечания ещё не обновлены':'\nАвторазметка устарела';for(const issue of issues)text+='\n'+(reasons[issue.code]||issue.code);const access=accessReport()?.rows.find(r=>r.cell===k);if(access)text+='\n'+access.title+'\n'+(accessReasons[access.status]||access.status);$('details').textContent=text;
 $('override').value=Object.hasOwn(overrides,k)?(overrides[k]===null?'off':String(overrides[k])):'auto';
 showCell(k);showNeighbours(k);
}
function showNeighbours(key,current={}){if(!$('neighbourSection').open)return;const[x,y]=xy(key),target=$('neighbours');target.replaceChildren();for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){const k=(x+dx)+','+(y+dy),row=proposalAt(k),card=document.createElement('div');card.className='tile';const label=document.createElement('span');label.textContent=k+(row?' · '+row.template:P&&geomVersion===planVersion&&(P.preserved_land||[]).includes(k)?' · сохранённая локация / проход':layers.wall.has(k)||(P&&geomVersion===planVersion&&(P.generated_walls||[]).includes(k))?' · стена':layers.water.has(k)?' · вода':layers.rocks.has(k)?' · скалы':current[k]?' · '+current[k].id+' · '+current[k].title:' · суша');if(row){const image=document.createElement('img');image.loading='lazy';image.decoding='async';image.src='/art?id='+row.template+'&v='+(S.assets_revision||'1')+'-'+(S.catalog[row.template]?.art_key||row.template);image.alt='Родная карта '+row.template;card.append(image);}card.append(label);card.onclick=()=>go(k);target.append(card);}}

let cellData=null,cellRequest=0,mobDrag=null;const mobPending=new Set(),mobEdits=new Map();
$('neighbourSection').addEventListener('toggle',()=>{if(selected&&$('neighbourSection').open)showNeighbours(selected,cellData?.neighbours||{});});
async function showCell(key){
 const request=++cellRequest;$('cellActual').textContent='Читаю текущую локацию…';cellData=null;selectedTemplate=null;mobDrag=null;$('mobChoice').value='';$('local').hidden=true;$('mobOverlay').replaceChildren();$('art').style.display='none';
 try{const[x,y]=xy(key),r=await fetch('/cell?x='+x+'&y='+y);if(!r.ok)throw Error('Не удалось прочитать локацию');const data=await r.json();if(request!==cellRequest||selected!==key)return;cellData=data;
 $('cellActual').textContent='Текущая: '+(data.actual.binding_id??data.actual.id)+' · '+data.actual.title+' · '+data.actual.name+'\nВыходы текущей локации: '+((data.actual.native_exits||[]).join(', ')||'нет');
 renderCell();showNeighbours(key,data.neighbours);
 }catch(error){if(request===cellRequest)$('cellActual').textContent=error.message;}
}
function withPatrol(view){
 if($('viewActual').checked||!overlays.patrol.has(selected))return view;
 const population=P?.patrol_population?.cells?.[selected],patch=S.patrol_mob_overrides?.[selected];
 if(!population||population.template!==view.id)return view;
 if(JSON.stringify([...population.occupied].sort((a,b)=>a-b))!==JSON.stringify(view.spawns.map(r=>r.cell).sort((a,b)=>a-b)))return view;
 const positions=patch?.template===view.id&&patch.signature===population.signature&&patch.positions?.length===population.positions.length?patch.positions:population.positions;
 const count=view.spawns.length,spawns=positions.map((cell,i)=>({index:count+i,patrol_index:i,origin:'patrol',cell,source_cell:population.positions[i],type:population.type_ids[i],level:population.levels[i],name:'Патруль Магриба · '+population.levels[i]+' ур.'}));
 return {...view,patrol:population,spawns:[...view.spawns,...spawns]};
}
function localView(){
 if(!cellData)return null;
 const row=proposalAt(selected);
 if(S.manual_editing&&!$('viewActual').checked&&!row&&((P?.depth_cells||[]).includes(selected)||layers.wall.has(selected)||layers.water.has(selected)||planWalls.has(selected)))return null;
 if(row&&!$('viewActual').checked){const c=S.catalog[row.template],population=P?.coastal_population?.cells?.[selected],patch=S.coastal_mob_overrides?.[selected],valid=population?.template===row.template,positions=valid&&patch?.template===row.template&&patch.signature===population.signature&&patch.positions?.length===population.positions.length?patch.positions:valid?population.positions:[];const spawns=positions.map((cell,index)=>({cell,index,type:population.type_id,name:'Крокодил · '+population.level+' ур. · '+population.city,level:population.level,source_cell:population.positions[index]}));return withPatrol({...row,id:row.template,art_key:c.art_key,name:c.name,width:c.width||64,height:c.height||128,spawns,coastal:valid?population:null});}
 if(!$('viewActual').checked&&cellData.planned){const view=cellData.planned,patch=S.mob_overrides?.[selected],valid=patch&&patch.location_id===view.id&&patch.spawn_signature===view.spawn_signature&&patch.positions?.length===view.spawns.length;return withPatrol({...view,spawns:view.spawns.map((m,i)=>({...m,cell:valid?patch.positions[i]:m.cell}))});}
 const actual=$('viewActual').checked?cellData.actual:(cellData.original||cellData.actual),patch=S.mob_overrides?.[selected];
 const valid=patch&&patch.location_id===actual.id&&patch.spawn_signature===actual.spawn_signature&&patch.positions?.length===actual.spawns.length;
 return withPatrol({...actual,spawns:actual.spawns.map((r,i)=>({...r,cell:valid?patch.positions[i]:r.cell}))});
}
const artURLs=new Map();let requestedArtURL=null,currentGeometryURL=null;
function renderArtwork(row){
 const art=$('art');
 if(!$('showArtwork').checked){art.style.display='none';$('artStatus').textContent='';return;}
 const key=row.art_key||String(row.id);
 if(!artURLs.has(key))artURLs.set(key,'/art?id='+row.id+'&v='+(S.assets_revision||'1')+'-'+key);
 const url=artURLs.get(key);
 const loaded=()=>{if(requestedArtURL!==url)return;art.style.display=$('showArtwork').checked?'block':'none';$('artStatus').textContent='Изображение локации загружено.';};
 if(requestedArtURL===url&&art.complete&&art.naturalWidth){loaded();return;}
 art.style.display='none';$('artStatus').textContent='Загружаю изображение локации…';art.onload=loaded;
 art.onerror=()=>{if(requestedArtURL!==url)return;requestedArtURL=null;art.style.display='none';$('artStatus').textContent='Не удалось загрузить изображение. Геометрия доступна отдельно.';};
 if(requestedArtURL!==url){requestedArtURL=url;art.src=url;}
}
function renderCell(){
 const row=localView();if(!row){selectedTemplate=null;$('local').hidden=true;$('art').style.display='none';$('mobOverlay').replaceChildren();$('templateName').textContent='Закрытая клетка: стена, русло или глубина';$('mobChoice').replaceChildren();syncMobSelection();$('mobStatus').textContent='Вход в клетку закрыт. Исходную карту можно посмотреть галочкой «Текущая локация из игры».';return;}selectedTemplate=row.id;$('local').hidden=false;const geometryURL='/template?id='+row.id+'&grid='+($('showHexes').checked?'1':'0')+'&background='+($('showArtwork').checked?'0':'1')+'&geometry='+($('showGeometry').checked?'1':'0')+'&v='+(S.assets_revision||'1')+'-'+(row.art_key||row.id);if(currentGeometryURL!==geometryURL){currentGeometryURL=geometryURL;$('local').src=geometryURL;}
 $('templateName').textContent=((row.mountain_trail||row.mountain_portal)?'Горные тропы · '+row.source_location+' → ':'')+row.id+' · '+row.name+((P?.depth_cells||[]).includes(selected)?' · закрыто глубиной':'')+(((proposalAt(selected)||row.planned_binding)&&!$('viewActual').checked)?' · предложение':' · текущая локация');
 renderArtwork(row);
 const choice=$('mobChoice').value;$('mobChoice').replaceChildren();for(const mob of row.spawns)$('mobChoice').add(new Option(mob.name+' · '+mob.type+' · '+(mob.cell%row.width)+','+Math.floor(mob.cell/row.width),String(mob.index)));
 $('mobChoice').value=row.spawns.some(m=>String(m.index)===choice)?choice:String(row.spawns[0]?.index??'');syncMobSelection();
 $('mobStatus').textContent=row.patrol?'Патруль Магриба · 19 ур. · HP ×2 · Голдовое оружие + чертёж на урон · Обычный опыт · Без лута. Бойцов: '+row.patrol.positions.length+'. Исходных обитателей: '+row.patrol.occupied.length+'. Позиции сохраняются отдельно в черновике.':row.coastal?row.coastal.city+' · '+row.coastal.level+' ур. · Крокодилов: '+row.spawns.length+'. Клыки: урон голдового холодного оружия своего уровня · Обычный опыт · Без лута. До входов/выходов ≥10 гексов; между мобами ≥12. Сдвиги сохраняются в черновике.':row.spawns.length?'Настроенных обитателей: '+row.spawns.length+'. Сдвиги сохраняются только в черновике.':P?.coastal_population?.excluded?.[selected]==='isolated_eden'?'Эдем: крокодилов нет.':P?.coastal_population?.excluded?.[selected]==='dry_connector'?'Сухой соединительный участок: крокодилов нет.':P?.coastal_population?.enabled&&row.kind==='coast'?'Для этой клетки крокодилы не назначены: проверь доступность, зону города и обнови переходы.':'Настроенных мобов нет. Для новой границы мобы исходного шаблона не копируются.';
 if(installedReadOnly())$('mobStatus').textContent+=' Установленная копия доступна только для сравнения. Для редактирования сними галочку «Текущая локация из игры».';
 drawMobs();
}
const spriteRequests=new Map();
function spriteInfo(type){if(!spriteRequests.has(type))spriteRequests.set(type,fetch('/mob-sprite-info?type='+type).then(async r=>{if(!r.ok)throw Error('Модель недоступна');return r.json();}).catch(error=>{spriteRequests.delete(type);throw error;}));return spriteRequests.get(type);}
function drawMobs(){
 const row=localView(),svg=$('mobOverlay');svg.replaceChildren();if(!row)return;svg.setAttribute('viewBox','0 0 '+(row.width*40)+' '+(row.height*15));svg.style.display=$('showMobs').checked?'block':'none';
 for(const mob of [...row.spawns].sort((a,b)=>a.cell-b.cell)){
  const group=document.createElementNS('http://www.w3.org/2000/svg','g');group.setAttribute('data-mob',mob.index);group.setAttribute('transform','translate('+(40*(mob.cell%row.width)+20*(Math.floor(mob.cell/row.width)%2))+' '+(15*Math.floor(mob.cell/row.width))+')');
  const anchor=document.createElementNS('http://www.w3.org/2000/svg','circle');anchor.setAttribute('r','13');anchor.setAttribute('fill',mob.origin==='patrol'?'#be7dff':'#ee4343');anchor.setAttribute('stroke','#fff');anchor.setAttribute('stroke-width','2');group.append(anchor);
  const title=document.createElementNS('http://www.w3.org/2000/svg','title');title.textContent=mob.name+' · '+mob.type;group.append(title);svg.append(group);
  if($('showMobs').checked)spriteInfo(mob.type).then(info=>{if(!group.isConnected)return;const image=document.createElementNS('http://www.w3.org/2000/svg','image');image.setAttribute('href',info.url);image.setAttribute('x',info.ox);image.setAttribute('y',info.oy);image.setAttribute('width',info.width);image.setAttribute('height',info.height);group.append(image);}).catch(()=>{});
 }
}

async function moveMob(index,target){
 const key=selected,actual=$('viewActual').checked?cellData?.actual:(cellData?.original||cellData?.actual),view=localView();
 if($('viewActual').checked&&actual?.installed_snapshot)throw Error('Это установленная копия для сравнения. Сними «Текущая локация из игры», чтобы менять расстановку в черновике.');
 if(!view||!Number.isInteger(index)||index<0||index>=view.spawns.length)throw Error('Выбери моба');
 const mob=view.spawns[index],patrol=mob.origin==='patrol',coastal=!!view.coastal&&!patrol;
 const actorSource=view.planned_binding?view:actual;
 if(!patrol&&!coastal&&(!actorSource||view.id!==actorSource.id))throw Error('Для изменения исходных мобов включи текущую локацию');
 if(mobPending.has(key))throw Error('Дождись проверки предыдущего перемещения');
 const roster=patrol?view.spawns.filter(r=>r.origin==='patrol'):view.spawns.filter(r=>r.origin!=='patrol');
 const positions=roster.map(r=>r.cell);positions[patrol?mob.patrol_index:index]=target;
 const patch=patrol?{template:view.id,signature:view.patrol.signature,positions}:coastal?{template:view.id,signature:view.coastal.signature,positions}:{location_id:actorSource.id,spawn_signature:actorSource.spawn_signature,positions};
 const field=patrol?'patrol_mob_overrides':coastal?'coastal_mob_overrides':'mob_overrides';
 const version=mobEdits.get(key)||0;mobPending.add(key);syncMobSelection();
 try{
  const verified=await post(patrol?'/validate-patrol-mobs':coastal?'/validate-coastal-mobs':'/validate-mobs',patrol?{...payload(),[field]:{[key]:patch}}:{[field]:{[key]:patch}});
  if((mobEdits.get(key)||0)!==version)return;
  S[field]??={};S[field][key]=verified[key];dirty=true;editVersion++;
  if(selected===key){renderCell();$('mobStatus').textContent='Позиция изменена в черновике. Нажми «Сохранить черновик».';}
 }finally{mobPending.delete(key);if(selected===key)syncMobSelection();}
}
$('showArtwork').onchange=renderCell;$('showGeometry').onchange=renderCell;$('showHexes').onchange=renderCell;$('viewActual').onchange=renderCell;$('showMobs').onchange=drawMobs;
function installedReadOnly(){return $('viewActual').checked&&!!cellData?.actual?.installed_snapshot;}
function syncMobSelection(){const view=localView(),mob=view?.spawns.find(m=>String(m.index)===$('mobChoice').value),readonly=installedReadOnly();$('mobX').value=mob?mob.cell%view.width:'';$('mobY').value=mob?Math.floor(mob.cell/view.width):'';$('moveMob').disabled=readonly||!mob||mobPending.has(selected);for(const id of ['mobX','mobY','moveMobs','resetMobs'])$(id).disabled=readonly||!view;}
$('mobChoice').onchange=syncMobSelection;
$('moveMob').onclick=async()=>{try{const view=localView(),x=+$('mobX').value,y=+$('mobY').value;if(!view||!Number.isInteger(x)||!Number.isInteger(y)||x<0||x>=view.width||y<0||y>=view.height)throw Error('Координаты вне локации');await moveMob(+$('mobChoice').value,y*view.width+x);}catch(error){$('mobStatus').textContent=error.message;}};
$('resetMobs').onclick=()=>{if(!cellData||installedReadOnly())return;const view=localView(),mob=view?.spawns.find(m=>String(m.index)===$('mobChoice').value),patrol=mob?.origin==='patrol',coastal=!!view?.coastal&&!patrol;mobEdits.set(selected,(mobEdits.get(selected)||0)+1);if(patrol)delete S.patrol_mob_overrides?.[selected];else if(coastal)delete S.coastal_mob_overrides?.[selected];else{delete S.mob_overrides?.[selected];cellData.actual.spawns=cellData.actual.spawns.map(r=>({...r,cell:r.source_cell}));}dirty=true;editVersion++;renderCell();};
function hexCell(pt){const row=Math.floor(pt.y/15),d=pt.y-row*15-7.5;let a;if(Math.abs(d)>2.5)a=d>=0?1:0;else{const x4=pt.x-20*(row%2),t=20-Math.abs(x4-Math.floor((x4+20)/40)*40),y9=pt.y-row*15-5;a=y9<=Math.abs(t/4)?0:1;}const y=row+a;return {x:Math.floor(pt.x/40-.5*(y%2)+.5),y};}
function mobPoint(e){const row=localView(),r=$('local').getBoundingClientRect(),w=r.width-2,h=r.height-2,scale=Math.min(w/(row.width*40),h/(row.height*15));return {x:(e.clientX-r.left-1-(w-row.width*40*scale)/2)/scale,y:(e.clientY-r.top-1-(h-row.height*15*scale)/2)/scale};}
$('mobOverlay').addEventListener('pointerdown',e=>{if(e.button!==0||!$('moveMobs').checked||mobPending.has(selected))return;const target=e.target.closest('[data-mob]');if(!target)return;e.preventDefault();e.stopPropagation();mobDrag={index:+target.getAttribute('data-mob'),element:target};$('mobOverlay').setPointerCapture(e.pointerId);});
$('mobOverlay').addEventListener('pointermove',e=>{if(!mobDrag)return;const pt=hexCell(mobPoint(e));mobDrag.element.setAttribute('transform','translate('+(40*pt.x+20*(pt.y%2))+' '+(15*pt.y)+')');});
$('mobOverlay').addEventListener('pointerup',async e=>{if(!mobDrag)return;const index=mobDrag.index;mobDrag=null;const pt=hexCell(mobPoint(e)),row=localView();try{if(pt.x<0||pt.y<0||pt.x>=row.width||pt.y>=row.height)throw Error('Координаты вне локации');await moveMob(index,Math.floor(pt.y)*row.width+Math.floor(pt.x));}catch(error){drawMobs();$('mobStatus').textContent=error.message;}});
const cancelMobDrag=()=>{mobDrag=null;drawMobs();};$('mobOverlay').addEventListener('pointercancel',cancelMobDrag);$('mobOverlay').addEventListener('lostpointercapture',cancelMobDrag);
for(const id of MODES)$(id).onclick=()=>{mode=id;for(const name of MODES)$(name).setAttribute('aria-pressed',name===id?'true':'false');};
$('size').oninput=e=>{brush=+e.target.value;$('brushValue').textContent=brush;};$('opacity').oninput=e=>{$('alpha').textContent=e.target.value+'%';dirty=true;editVersion++;render();};for(const id of ['manual','showauto','showplaces',...Object.values(COLOR_SWITCH),'colorIssues','colorPatrol','colorTunnels'])$(id).onchange=render;
$('zoom').oninput=e=>setZoom(+e.target.value/100);$('wrap').addEventListener('wheel',e=>{if(e.ctrlKey){e.preventDefault();setZoom(zoom*(e.deltaY<0?1.2:1/1.2));}},{passive:false});
function cellAt(e){const r=$('map').getBoundingClientRect();return [S.bounds[0]+Math.floor((e.clientX-r.left)/zoom/6),S.bounds[1]+Math.floor((e.clientY-r.top)/zoom/6)];}

function stampManual(key){
 if(mode==='patrol'||mode==='tunnels'){if(overlays[mode].has(key))return false;overlays[mode].add(key);return true;}
 let removed=false;
 if(mode==='erase'&&['patrol','tunnels','all'].includes($('eraseLayer').value)){
  for(const name of ['patrol','tunnels'])if($('eraseLayer').value===name||$('eraseLayer').value==='all')removed=overlays[name].delete(key)||removed;
  if($('eraseLayer').value!=='all')return removed;
 }
 const old=Object.keys(layers).find(name=>layers[name].has(key)),row=proposalAt(key);
 if(mode==='erase'){
  if(old===undefined&&!row&&!planWalls.has(key)&&(!(P?.depth_cells||[]).includes(key)||sceneEdits[key]==='erase'))return removed;
  const river=old==='water'&&row?.kind==='coast';
  for(const set of Object.values(layers))set.delete(key);
  if(river)layers.water.add(key);
  overrides[key]=null;sceneEdits[key]=river?'water':'erase';
 }else{
  if(old===mode&&sceneEdits[key]===mode&&overrides[key]===undefined)return false;
  for(const set of Object.values(layers))set.delete(key);
  layers[mode].add(key);delete overrides[key];sceneEdits[key]=mode;
 }
 return true;
}
function stamp(x,y){
 const r=Math.floor(brush/2);let modified=false;
 for(let dx=-r;dx<=r;dx++)for(let dy=-r;dy<=r;dy++){
  const a=x+dx,b=y+dy;if(!inBounds(a,b))continue;const k=a+','+b;
  if(painting){if(strokeCells.has(k))continue;strokeCells.add(k);}
  if(S.manual_editing||mode==='patrol'||mode==='tunnels'){modified=stampManual(k)||modified;continue;}
  const old=Object.keys(layers).find(name=>layers[name].has(k)),next=mode==='erase'?undefined:mode;
  const generated=$('showauto').checked&&P?.placements[k]&&old===planMarks.get(k)&&overrides[k]===planOverrides[k];
  const generatedWall=$('showauto').checked&&planWalls.has(k)&&old===planMarks.get(k)&&overrides[k]===planOverrides[k];
  if(mode==='erase'&&(old==='wall'||generatedWall)){
   for(const set of Object.values(layers))set.delete(k);
   overrides[k]=null;modified=true;continue;
  }
  if(mode==='erase'&&(old==='coast'||generated)){
   // Remove the proposed shore/rock without punching through its water or
   // wall backing. The suppression survives recalculation and draft saves.
   if(old==='coast')layers.coast.delete(k);
   overrides[k]=null;modified=true;continue;
  }
  if(old===next)continue;
  for(const set of Object.values(layers))set.delete(k);
  if(next)layers[next].add(k);if(mode==='erase')overrides[k]=null;else delete overrides[k];modified=true;
 }
 return modified;
}
function paint(e){const raw=cellAt(e),target=[Math.max(S.bounds[0],Math.min(S.bounds[2],raw[0])),Math.max(S.bounds[1],Math.min(S.bounds[3],raw[1]))];let[x,y]=last||target;const[tx,ty]=target,dx=Math.abs(tx-x),dy=-Math.abs(ty-y),sx=x<tx?1:-1,sy=y<ty?1:-1;let error=dx+dy,modified=false;while(true){modified=stamp(x,y)||modified;if(x===tx&&y===ty)break;const q=2*error;if(q>=dy){error+=dy;x+=sx;}if(q<=dx){error+=dx;y+=sy;}}last=target;if(modified)changed();}
$('over').addEventListener('pointerdown',e=>{if(!S)return;if(e.button===1){e.preventDefault();pan={x:e.clientX,y:e.clientY,left:$('wrap').scrollLeft,top:$('wrap').scrollTop};$('over').style.cursor='grabbing';$('over').setPointerCapture(e.pointerId);return;}if(e.button!==0||pan)return;const[x,y]=cellAt(e);if(!inBounds(x,y))return;if(mode==='inspect'){inspect(x+','+y);return;}undo.push(editSnapshot());if(undo.length>20)undo.shift();painting=true;last=null;strokeCells.clear();$('over').setPointerCapture(e.pointerId);paint(e);});
$('over').addEventListener('pointermove',e=>{if(pan){$('wrap').scrollLeft=pan.left+pan.x-e.clientX;$('wrap').scrollTop=pan.top+pan.y-e.clientY;}else if(painting)paint(e);});function endPointer(){painting=false;last=null;pan=null;strokeCells.clear();$('over').style.cursor='crosshair';}window.addEventListener('pointerup',endPointer);$('over').addEventListener('pointercancel',endPointer);$('over').addEventListener('lostpointercapture',endPointer);$('over').addEventListener('auxclick',e=>{if(e.button===1)e.preventDefault();});
$('undo').onclick=()=>{if(undo.length){const previous=undo.pop();layers=previous.layers;overrides=previous.overrides;sceneEdits=previous.scenes||{};overlays=previous.overlays||{patrol:new Set(),tunnels:new Set()};if(S.manual_editing&&previous.plan){P=previous.plan;planMarks=previous.marks;planOverrides=previous.reviewedOverrides;planScenes=previous.reviewedScenes;planWalls=new Set(P.generated_walls||[]);updateStats();}changed();}};
$('goto').onclick=()=>go($('gx').value.trim()+','+$('gy').value.trim());$('issues').onchange=e=>{if(e.target.value)go(e.target.value);};
$('setOverride').onclick=()=>{if(!selected){message('Сначала выбери клетку');return;}const value=$('override').value;if(value==='auto')delete overrides[selected];else{overrides[selected]=value==='off'?null:+value;if(S.manual_editing&&value!=='off'){const kind=S.catalog[+value].kind==='rock'?'rocks':'coast';for(const set of Object.values(layers))set.delete(selected);layers[kind].add(selected);sceneEdits[selected]=kind;}}changed();if(S.manual_editing)inspect(selected);};

$('outlineWalls').onclick=async()=>{
 const button=$('outlineWalls'),version=geomVersion;button.disabled=true;message('Создаю один ряд пограничных карт перед стенами…');
 try{const result=await post('/outline-walls',payload());if(version!==geomVersion){message('Разметка изменилась во время подготовки. Результат не применён; нажми кнопку снова.');return;}
 const entries=Object.entries(result.additions);if(!entries.length){message('Свободных клеток для новой обводки нет. Существующие карты сохранены.');return;}
 undo.push(editSnapshot());
 for(const[key,row]of entries){const kind=row.kind==='rock'?'rocks':'coast';layers[kind].add(key);sceneEdits[key]=kind;overrides[key]=row.template;}
 changed();showReviewedPlan(result.plan,geomVersion);message('Добавлено пограничных карт: '+entries.length+'. Замечания отмечены; изменения ещё не сохранены.');
 }catch(error){message(error.message);}finally{button.disabled=false;}
};
$('calculate').onclick=async()=>{const button=$('calculate'),version=geomVersion;button.disabled=true;message('Обновляю родные переходы и замечания без перестройки границ…');try{const result=await post('/calculate',payload());if(version!==geomVersion){message('Во время расчёта разметка изменилась. Нужен новый пересчёт.');return;}showReviewedPlan(result,version);message('Переходы и замечания обновлены. Ручные назначения и соседние границы не перестроены.');}catch(error){message(error.message);}finally{button.disabled=false;}};
$('repairBorders').onclick=async()=>{
 const button=$('repairBorders'),version=editVersion;button.disabled=true;message('Подбираю родные препятствия и пограничный ряд перед стенами и водой…');
 try{const result=await post('/repair-boundaries',payload());if(version!==editVersion){message('Во время подготовки были новые правки. Результат не применён; нажми кнопку снова.');return;}
 undo.push(editSnapshot());const d=result.draft;
 const water=new Set(d.water),rocks=new Set(d.rocks);layers={water,rocks,coast:new Set(d.coast||[]),wall:new Set(d.blocked.filter(k=>!water.has(k)&&!rocks.has(k)))};
 overlays={patrol:new Set(d.patrol||[]),tunnels:new Set(d.tunnels||[])};S.mountain_trails=!!d.mountain_trails;S.physical_boundary_audit=true;overrides={...d.overrides};sceneEdits={...d.scene_edits};changed();showReviewedPlan(result.plan,geomVersion);
 message('Исправление подготовлено. Спорных клеток: '+result.report.before+' → '+result.plan.summary.unresolved+'. Изменения можно отменить; черновик ещё не сохранён.');
 }catch(error){message(error.message);}finally{button.disabled=false;}
};
$('save').onclick=async()=>{const button=$('save'),version=editVersion,geometry=geomVersion,review=reviewEpoch;button.disabled=true;message('Сохраняю отдельную копию…');try{const result=await post('/save',payload());S.revision=result.revision;if(version===editVersion)dirty=false;
 // The server already reviewed exactly this saved geometry. Refresh its
 // markers, without starting another calculation or replacing newer edits.
 if(result.plan&&geometry===geomVersion&&review===reviewEpoch)showReviewedPlan(result.plan,geometry);
 message('Черновик сохранён. Игровые данные не изменены.'+(dirty?' Остались изменения на экране.':''));}catch(error){message(error.message);}finally{button.disabled=false;}};
$('testRoute').onclick=async()=>{if(geomVersion!==planVersion&&!S.manual_editing){message('Сначала пересчитай границы');return;}const version=geomVersion;try{const r=await post('/route',{...payload(),start:$('routeStart').value.trim(),end:$('routeEnd').value.trim()});if(version!==geomVersion)return;routePath=r.path;$('routeResult').textContent=r.reachable?'Путь доступен: '+(r.path.length-1)+' переходов':r.reason;draw();}catch(error){$('routeResult').textContent=error.message;}};
$('local').onclick=e=>{const row=localView();if(!row)return;const pt=hexCell(mobPoint(e));if(pt.x<0||pt.y<0||pt.x>=row.width||pt.y>=row.height)return;$(localPick++%2?'localEnd':'localStart').value=pt.y*row.width+pt.x;};
$('testLocal').onclick=async()=>{if(selectedTemplate===null){$('localResult').textContent='Выбери назначенную локацию';return;}try{const r=await post('/local-probe',{template:selectedTemplate,start:+$('localStart').value,end:+$('localEnd').value});$('localResult').textContent=r.reachable?'Гексы связаны разрешённой локальной геометрией':'Путь закрыт препятствием или гексы не связаны';}catch(error){$('localResult').textContent=error.message;}};
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
$('previewSize').oninput=e=>{$('local').style.height=e.target.value+'px';$('previewSizeValue').textContent=e.target.value+' px';};
let resizingAside=null;
$('resizeAside').addEventListener('pointerdown',e=>{if(e.button!==0)return;e.preventDefault();resizingAside=e.pointerId;$('resizeAside').setPointerCapture(e.pointerId);});
$('resizeAside').addEventListener('pointermove',e=>{if(resizingAside===null)return;const area=$('main').getBoundingClientRect();$('sidebar').style.width=Math.max(280,Math.min(area.width*.8,area.right-e.clientX))+'px';});
const stopAsideResize=()=>{resizingAside=null;};
$('resizeAside').addEventListener('pointerup',stopAsideResize);$('resizeAside').addEventListener('pointercancel',stopAsideResize);$('resizeAside').addEventListener('lostpointercapture',stopAsideResize);
$('resizeAside').addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();const area=$('main').getBoundingClientRect();const width=$('sidebar').getBoundingClientRect().width;$('sidebar').style.width=Math.max(280,Math.min(area.width*.8,width+(e.key==='ArrowLeft'?40:-40)))+'px';});
(async()=>{try{const r=await fetch('/state');if(!r.ok)throw Error('Не удалось загрузить копию');S=await r.json();layers.water=new Set(S.water);layers.rocks=new Set(S.rocks);layers.coast=new Set(S.coast||[]);layers.wall=new Set(S.blocked.filter(k=>!layers.water.has(k)&&!layers.rocks.has(k)));overlays={patrol:new Set(S.patrol||[]),tunnels:new Set(S.tunnels||[])};overrides={...S.overrides};sceneEdits={...(S.scene_edits||{})};P=S.plan;capturePlan();
 const width=(S.bounds[2]-S.bounds[0]+1)*6,height=(S.bounds[3]-S.bounds[1]+1)*6;cache.width=width;cache.height=height;$('over').width=width;$('over').height=height;$('map').src='/map.png';$('map').width=width;$('map').height=height;$('stage').style.width=width+'px';$('stage').style.height=height+'px';$('opacity').value=S.opacity;$('alpha').textContent=S.opacity+'%';
 for(const[id,row]of Object.entries(S.catalog))$('override').add(new Option(id+' · '+(row.kind==='coast'?'Берег':'Скалы')+' · '+row.closed.join(''),id));
 $('source').textContent='Исходный снимок '+S.source.sha256.slice(0,12)+(S.applied_game?' · доступно сравнение с установленной тестовой сборкой':' · предпросмотр границ');setZoom(1);updateStats();render();message('Черновик загружен. Сохранение в редакторе меняет только черновик.');go('5997,1679');
 }catch(error){message(error.message);}})();
</script></html>"""
