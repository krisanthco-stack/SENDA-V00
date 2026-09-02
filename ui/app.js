const $ = id => document.getElementById(id);
const qsa = s => [...document.querySelectorAll(s)];
const isGitHubPages = location.hostname.endsWith('github.io');
const state = {
  health:null,
  module:'inicio',
  info:{type:'TODOS',offset:0,pageSize:25,total:0,rows:[],selected:new Map()},
  control:{selectedId:null,type:'TODOS',offset:0,pageSize:25,total:0,detail:null},
  management:{rows:[]}
};

function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function toast(msg){const e=$('toast');e.textContent=msg;e.classList.add('show');setTimeout(()=>e.classList.remove('show'),3400)}
function filters(extra={}){return {year:$('filterYear').value,quarter:$('filterQuarter').value,month:$('filterMonth').value,district:$('filterDistrict').value,alarm:$('filterAlarm').value,...extra}}
function query(obj){const p=new URLSearchParams;Object.entries(obj||{}).forEach(([k,v])=>{if(v!==undefined&&v!==null&&v!==''&&!['TODOS','TODAS','ALL'].includes(String(v)))p.set(k,v)});return p.toString()}
function apiUnavailableMessage(){return 'Esta vista no está conectada al servidor local de SENDA. Abra INICIAR_SENDA_V0.bat y use http://127.0.0.1:8765.'}
async function api(path,options){
  if(isGitHubPages)throw new Error(apiUnavailableMessage());
  const r=await fetch(path,options);const contentType=(r.headers.get('content-type')||'').toLowerCase();const text=await r.text();
  if(!contentType.includes('application/json')){
    if(/^\s*<!doctype|^\s*<html|^\s*</i.test(text))throw new Error(`El servidor devolvió HTML en lugar de JSON (${path}). Abra SENDA desde http://127.0.0.1:8765.`);
    throw new Error(`Respuesta no válida del servidor (${path}) · HTTP ${r.status}`);
  }
  let j;try{j=text?JSON.parse(text):{}}catch{throw new Error(`Respuesta JSON dañada del servidor (${path}).`)}
  if(!r.ok||j.ok===false)throw new Error(j.error||`HTTP ${r.status}`);return j;
}
function moduleView(name){
  state.module=name;qsa('.nav').forEach(b=>b.classList.toggle('active',b.dataset.module===name));qsa('.view').forEach(v=>v.classList.toggle('active',v.dataset.view===name));
  if(name==='inicio')loadDashboard();if(name==='informacion')loadInformation();if(name==='control')loadControl();if(name==='gestion')loadManagement();
}
qsa('.nav').forEach(b=>b.onclick=()=>moduleView(b.dataset.module));

async function health(){
  if(isGitHubPages){$('serverDot').className='dot';$('serverState').textContent='Vista web';$('serverDetail').textContent='Abra SENDA local para usar datos';$('dataPath').textContent='GitHub Pages no ejecuta la API local.';return}
  try{const h=await api('/api/health');state.health=h;$('serverDot').className='dot ok';$('serverState').textContent='Servidor conectado';$('serverDetail').textContent=`${h.version} ${h.engine_version||''}`;$('dataPath').textContent=h.data_dir||'—'}
  catch(e){$('serverDot').className='dot bad';$('serverState').textContent='Servidor no disponible';$('serverDetail').textContent=e.message}
}
function barChart(id,data){const box=$(id),entries=Object.entries(data||{}).sort((a,b)=>b[1]-a[1]),max=Math.max(1,...entries.map(x=>x[1]));box.innerHTML=entries.length?entries.map(([k,v])=>`<div class="bar"><i style="height:${Math.max(4,Math.round(v/max*120))}px"></i><b>${Number(v).toLocaleString('es-CR')}</b><small title="${esc(k)}">${esc(k)}</small></div>`).join(''):'<small>Sin datos para el filtro.</small>'}
function alarmPill(a){return `<span class="pill ${a}">${a==='red'?'🔴 Roja':a==='yellow'?'🟡 Amarilla':'🟢 Verde'}</span>`}
function statusPill(s){const cls=s==='EN CONTROL'?'control':s==='GESTION'?'gestion':'info';return `<span class="status ${cls}">${esc(s||'INFORMACION')}</span>`}
function movementLabel(r){return r.categoria||r.tipo||r.fuente||'OTROS'}

async function loadDashboard(){
  try{
    const f=filters(),qs=query(f),d=await api('/api/dashboard?'+qs),m=await api('/api/movements?limit=80&'+qs);
    $('kMov').textContent=Number(d.movimientos||0).toLocaleString('es-CR');$('kFolios').textContent=Number(d.folios||0).toLocaleString('es-CR');$('kWorkflowMov').textContent=Number(d.movimientos_tramite||0).toLocaleString('es-CR');$('kControl').textContent=d.casos_control||0;$('kGestion').textContent=d.casos_gestion||0;$('kRed').textContent=d.alarmas.red||0;
    $('ctxPending').textContent=d.folios||0;$('ctxControl').textContent=d.casos_control||0;$('ctxGestion').textContent=d.casos_gestion||0;$('ctxRed').textContent=d.alarmas.red||0;$('ctxYellow').textContent=d.alarmas.yellow||0;$('ctxGreen').textContent=d.alarmas.green||0;$('ctxYear').textContent=f.year;$('ctxQuarter').textContent=f.quarter;$('ctxMonth').textContent=f.month;$('ctxDistrict').textContent=f.district;
    $('dashboardScope').textContent=[f.year,f.quarter,f.month,f.district,f.alarm].join(' · ');barChart('categoryBars',d.por_categoria);barChart('districtBars',d.por_distrito);
    $('recentRows').innerHTML=(m.rows||[]).slice(0,30).map(r=>`<tr><td><b>${esc(r.folio||'—')}</b></td><td>${esc(r.plano||'—')}</td><td>${esc(r.fecha||'—')}</td><td>${esc(movementLabel(r))}</td><td>${esc(r.codigo||'—')}</td><td>${esc(r.operacion||'—')}</td><td>${statusPill(r.estado_expediente)}</td><td>${alarmPill(r.alarma)}</td></tr>`).join('');
    await loadImports();
  }catch(e){toast(e.message)}
}
async function loadImports(){try{const r=await api('/api/imports');const by={};(r.rows||[]).forEach(x=>{const y=x.anio||'—';(by[y]??=new Set).add(x.trimestre)});$('quarterHistory').innerHTML=Object.entries(by).slice(0,5).map(([y,s])=>`<div><b>${y}</b> · ${['T1','T2','T3','T4'].map(q=>s.has(q)?q+' ✓':q+' ○').join(' · ')}</div>`).join('')||'Sin cargas registradas.'}catch{$('quarterHistory').textContent='Sin historial.'}}

// ---------- importación robusta ----------
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function lastImportId(){try{const r=await api('/api/imports?limit=1');return Number(r.rows?.[0]?.id||0)}catch{return 0}}
async function recoverUpload(file,year,quarter,district,beforeId){
  $('importStatus').textContent=`${file.name} fue enviado. Verificando el resultado en SENDA…`;let offline=0;
  for(;;){
    try{await api('/api/health');offline=0;const r=await api('/api/imports?limit=50');const row=(r.rows||[]).find(x=>Number(x.id||0)>beforeId&&Number(x.anio||0)===Number(year)&&String(x.trimestre||'')===String(quarter)&&String(x.source_name||'').split(', ').includes(file.name));if(row){if(row.status==='COMPLETED')return {ok:true,inserted:Number(row.records||0),skipped:Number(row.skipped||0),errors:Number(row.errors||0),import_id:row.id,recovered:true};if(row.status==='FAILED')throw new Error(`La importación falló en el servidor: ${file.name}`);$('importStatus').textContent=`Procesando ${file.name}… servidor conectado`}else $('importStatus').textContent=`Esperando confirmación de ${file.name}… servidor conectado`}
    catch(e){if(String(e.message||'').startsWith('La importación falló'))throw e;if(++offline>=10)throw new Error('Servidor local no disponible. Ejecute INICIAR_SENDA_V0.bat y vuelva a intentar.')}
    await sleep(1000);
  }
}
async function uploadOne(file,year,quarter,district,index,total){const beforeId=await lastImportId();return new Promise((resolve,reject)=>{const x=new XMLHttpRequest(),url=`/api/upload?${query({year,quarter,district})}`;let uploadComplete=false,recovering=false;x.open('POST',url);x.timeout=0;x.setRequestHeader('Content-Type','application/octet-stream');x.setRequestHeader('X-Filename',file.name);x.upload.onprogress=e=>{if(e.lengthComputable){const overall=((index+e.loaded/e.total)/total)*100;$('uploadProgress').style.width=overall+'%';$('importStatus').textContent=`Subiendo ${file.name} · ${Math.round(e.loaded/e.total*100)}%`}};x.upload.onload=()=>{uploadComplete=true;$('importStatus').textContent=`${file.name} recibido · procesando en SENDA…`};const recover=()=>{if(recovering)return;recovering=true;if(!uploadComplete)return reject(new Error(`La transferencia de ${file.name} se interrumpió antes de completarse.`));recoverUpload(file,year,quarter,district,beforeId).then(resolve,reject)};x.onload=()=>{let j;try{j=JSON.parse(x.responseText)}catch{return recover()}if(x.status>=400||j.ok===false)return reject(new Error(j.error||`HTTP ${x.status}`));resolve(j)};x.onerror=recover;x.onabort=recover;x.send(file)})}
async function importFiles(){
  if(isGitHubPages){$('importStatus').textContent='La importación requiere SENDA local.';return toast('Importación disponible únicamente con el servidor local.')}
  const files=[...$('importFiles').files];if(!files.length)return toast('Seleccione uno o más archivos.');try{await api('/api/health')}catch{$('importStatus').textContent='ERROR · Servidor local no disponible.';return toast('Servidor local no disponible.')}
  files.sort((a,b)=>(!a.name.toUpperCase().includes('CATALOGO_COD_'))-(!b.name.toUpperCase().includes('CATALOGO_COD_')));const y=$('importYear').value,q=$('importQuarter').value,d=$('importDistrict').value;let total=0;
  try{for(let i=0;i<files.length;i++){const r=await uploadOne(files[i],y,q,d,i,files.length);total+=r.inserted||0}$('uploadProgress').style.width='100%';$('importStatus').textContent=`Carga completada · ${total.toLocaleString('es-CR')} registros nuevos`;toast('Importación completada');await loadDashboard();if(state.module==='informacion')await loadInformation(true)}catch(e){$('importStatus').textContent='ERROR · '+e.message;toast(e.message)}
}

// ---------- Información SENDA ----------
function updateInfoSelection(){
  $('infoSelectedCount').textContent=`${state.info.selected.size} seleccionados`;$('infoToControl').disabled=state.info.selected.size===0;
  qsa('#infoRows input[type=checkbox][data-key]').forEach(cb=>cb.checked=state.info.selected.has(cb.dataset.key));
}
function infoCategorySummary(c){return Object.entries(c||{}).filter(([,n])=>n).map(([k,n])=>`${k} ${n}`).join(' · ')||'Sin movimientos'}
async function loadInformation(reset=false){
  if(reset)state.info.offset=0;state.info.pageSize=Number($('infoPageSize').value||25);
  try{
    const params=filters({movement_type:state.info.type,search:$('infoSearch').value,page_size:state.info.pageSize,offset:state.info.offset}),r=await api('/api/information?'+query(params));state.info.rows=r.rows||[];state.info.total=r.total||0;
    $('infoTotalBadge').textContent=state.info.total;$('infoControlBadge').textContent=state.info.rows.filter(x=>x.status==='EN CONTROL').length;
    $('infoRows').innerHTML=state.info.rows.map((x,i)=>{const key=`${x.folio||''}|${x.plano||''}`;return `<tr><td><input type="checkbox" data-key="${esc(key)}" data-folio="${esc(x.folio||'')}" data-plano="${esc(x.plano||'')}"></td><td><b>${esc(x.folio||'—')}</b><div class="tiny">${esc(infoCategorySummary(x.categorias))}</div></td><td>${esc(x.plano||'—')}</td><td>${esc(x.distrito||'—')}</td><td>${x.derechos||0}</td><td><b>${x.movimientos||0}</b></td><td>${esc(x.first_date||'—')}</td><td>${esc(x.last_date||'—')}</td><td>${statusPill(x.status)}</td><td>${alarmPill(x.alarma)}</td><td><button class="btn mini info-view" data-folio="${esc(x.folio||'')}" data-plano="${esc(x.plano||'')}">VER</button></td></tr>`}).join('')||'<tr><td colspan="11">Sin expedientes para el filtro.</td></tr>';
    const page=Math.floor(state.info.offset/state.info.pageSize)+1,pages=Math.max(1,Math.ceil(state.info.total/state.info.pageSize));$('infoPager').textContent=`Página ${page} de ${pages} · ${state.info.total} expedientes`;$('infoPrev').disabled=state.info.offset===0;$('infoNext').disabled=state.info.offset+state.info.pageSize>=state.info.total;$('infoSelectPage').checked=false;updateInfoSelection();
  }catch(e){toast(e.message)}
}
async function openInformationEntity(folio,plano){
  try{const r=await api('/api/information/movements?'+query({folio,plano,movement_type:state.info.type,page_size:25,offset:0}));$('infoDetail').classList.remove('hidden');$('infoDetail').innerHTML=`<div class="panel-head"><div><h2>${esc(folio||plano)}</h2><small>${r.total} movimientos · del más antiguo al más nuevo</small></div><button class="btn mini" id="closeInfoDetail">CERRAR</button></div><div class="rights-inline">${(r.rights||[]).map(x=>`<span class="right-chip">${esc(x.derecho)} · ${x.movimientos}</span>`).join('')}</div><div class="tablewrap"><table><thead><tr><th>Fecha</th><th>Derecho</th><th>Plano</th><th>Movimiento</th><th>Código</th><th>Operación</th><th>Titular</th></tr></thead><tbody>${(r.rows||[]).map(x=>`<tr><td>${esc(x.fecha||'—')}</td><td>${esc(x.derecho||'—')}</td><td>${esc(x.plano||'—')}</td><td>${esc(movementLabel(x))}</td><td>${esc(x.codigo||'—')}</td><td>${esc(x.operacion||'—')}</td><td>${esc(x.titular||'—')}</td></tr>`).join('')}</tbody></table></div>`;$('closeInfoDetail').onclick=()=>{$('infoDetail').classList.add('hidden')}}catch(e){toast(e.message)}
}
async function createManualCase(){const body={folio:$('manualFolio').value,plano:$('manualPlano').value,district:$('manualDistrict').value,note:$('manualNote').value};if(!body.folio&&!body.plano)return toast('Indique folio/finca o plano.');try{await api('/api/cases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});$('manualFolio').value='';$('manualPlano').value='';$('manualNote').value='';toast('Expediente agregado');await loadInformation(true)}catch(e){toast(e.message)}}
async function passSelectedToControl(){if(!state.info.selected.size)return;try{const items=[...state.info.selected.values()];const r=await api('/api/control/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({items})});state.info.selected.clear();toast(`${r.selected} expediente(s) enviados a Control`);await loadInformation(true);await loadDashboard();moduleView('control')}catch(e){toast(e.message)}}

// ---------- Control ----------
async function loadControl(){
  try{const r=await api('/api/control?search='+encodeURIComponent($('controlSearch').value));$('controlCount').textContent=(r.rows||[]).length;$('controlList').innerHTML=(r.rows||[]).map(c=>`<div class="control-item ${state.control.selectedId===c.id?'active':''}" data-case-id="${c.id}"><b>${esc(c.folio||c.plano||'Expediente '+c.id)}</b><small>${esc(c.distrito)} · ${esc(c.responsable||'Sin responsable')}</small><small>${esc(c.prioridad||'NORMAL')} · EN CONTROL</small></div>`).join('')||'<div class="empty">No hay trámites en Control.</div>';qsa('.control-item[data-case-id]').forEach(x=>x.onclick=()=>openControlCase(Number(x.dataset.caseId)))}catch(e){toast(e.message)}
}
async function openControlCase(id){
  try{const d=await api(`/api/cases/${id}`);state.control.selectedId=id;state.control.detail=d;state.control.offset=0;state.control.type='TODOS';$('controlTitle').textContent=d.case.folio||d.case.plano||`Expediente ${id}`;$('controlSubtitle').textContent=`${d.movimientos_total} movimientos · ${d.case.distrito}`;$('controlFinalize').disabled=false;$('controlEmpty').classList.add('hidden');$('controlBody').classList.remove('hidden');$('editFolio').value=d.case.folio||'';$('editPlano').value=d.case.plano||'';$('editDistrict').value=d.case.distrito||'SIN IDENTIFICAR';$('editResponsible').value=d.case.responsable||'';$('editPriority').value=d.case.prioridad||'NORMAL';$('editNote').value=d.case.note||'';$('rightsBox').innerHTML=(d.derechos||[]).map(x=>`<details class="right-detail"><summary>${esc(x.derecho)} · ${x.movimientos} movimiento(s)</summary><div>Primer movimiento: <b>${esc(x.primera_fecha||'—')}</b> · Último movimiento: <b>${esc(x.ultima_fecha||'—')}</b></div></details>`).join('')||'<span class="right-chip">Sin derechos vinculados</span>';$('controlAudit').innerHTML=(d.audit||[]).map(a=>`<div class="audit-event"><b>${esc(a.action)}</b> · ${esc(a.created_at)}<br>${esc(a.previous_status||'')} ${a.new_status?'→ '+esc(a.new_status):''}${a.note?'<br>'+esc(a.note):''}</div>`).join('')||'<div class="empty">Sin historial.</div>';qsa('[data-control-type]').forEach(b=>b.classList.toggle('active',b.dataset.controlType==='TODOS'));await loadControlMovements();await loadControl()}catch(e){toast(e.message)}
}
async function loadControlMovements(){if(!state.control.selectedId)return;state.control.pageSize=Number($('controlPageSize').value||25);try{const r=await api(`/api/cases/${state.control.selectedId}/movements?`+query({movement_type:state.control.type,page_size:state.control.pageSize,offset:state.control.offset}));state.control.total=r.total||0;$('controlMovementCount').textContent=`${r.total||0} movimientos`;$('controlMovementRows').innerHTML=(r.rows||[]).map(x=>`<tr><td>${esc(x.fecha||'—')}</td><td>${esc(x.derecho||'—')}</td><td>${esc(x.plano||'—')}</td><td>${esc(movementLabel(x))}</td><td>${esc(x.codigo||'—')}</td><td>${esc(x.operacion||'—')}</td><td>${esc(x.titular||'—')}</td></tr>`).join('')||'<tr><td colspan="7">Sin movimientos de esta categoría.</td></tr>';const page=Math.floor(state.control.offset/state.control.pageSize)+1,pages=Math.max(1,Math.ceil(state.control.total/state.control.pageSize));$('controlPager').textContent=`Página ${page} de ${pages}`;$('controlPrev').disabled=state.control.offset===0;$('controlNext').disabled=state.control.offset+state.control.pageSize>=state.control.total}catch(e){toast(e.message)}}
async function saveControlCase(){if(!state.control.selectedId)return;const body={folio:$('editFolio').value,plano:$('editPlano').value,distrito:$('editDistrict').value,responsable:$('editResponsible').value,prioridad:$('editPriority').value,note:$('editNote').value};try{await api(`/api/cases/${state.control.selectedId}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});toast('Expediente actualizado');await openControlCase(state.control.selectedId)}catch(e){toast(e.message)}}
async function finalizeControlCase(){if(!state.control.selectedId)return;if(!confirm('¿Finalizar este trámite? Saldrá de Información SENDA y Control y pasará a Gestión. Los movimientos originales se conservan.'))return;try{await api(`/api/cases/${state.control.selectedId}/finalize`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({note:$('editNote').value})});toast('Trámite finalizado y enviado a Gestión');state.control.selectedId=null;state.control.detail=null;$('controlFinalize').disabled=true;$('controlBody').classList.add('hidden');$('controlEmpty').classList.remove('hidden');$('controlTitle').textContent='SELECCIONE UN TRÁMITE';await loadControl();await loadInformation(true);await loadManagement();await loadDashboard()}catch(e){toast(e.message)}}

// ---------- Gestión ----------
async function loadManagement(){try{const r=await api('/api/management?search='+encodeURIComponent($('managementSearch').value));state.management.rows=r.rows||[];$('managementRows').innerHTML=state.management.rows.map(c=>`<tr><td><b>${esc(c.folio||'—')}</b></td><td>${esc(c.plano||'—')}</td><td>${esc(c.distrito)}</td><td>${esc(c.responsable||'—')}</td><td>${esc(c.prioridad||'NORMAL')}</td><td>${esc(c.finalized_at||'—')}</td><td>${esc(c.note||'—')}</td><td><button class="btn mini management-view" data-case-id="${c.id}">VER</button> <button class="btn mini management-return" data-case-id="${c.id}">REGRESAR A INFORMACIÓN SENDA</button></td></tr>`).join('')||'<tr><td colspan="8">No hay trámites finalizados.</td></tr>';qsa('.management-view').forEach(b=>b.onclick=()=>openManagementCase(Number(b.dataset.caseId)));qsa('.management-return').forEach(b=>b.onclick=()=>returnManagementCase(Number(b.dataset.caseId)))}catch(e){toast(e.message)}}
async function openManagementCase(id){try{const d=await api(`/api/cases/${id}`),m=await api(`/api/cases/${id}/movements?page_size=25`);$('managementDetail').classList.remove('hidden');$('managementDetail').innerHTML=`<div class="panel-head"><div><h2>${esc(d.case.folio||d.case.plano)}</h2><small>Gestión · ${d.movimientos_total} movimientos</small></div><button class="btn mini" id="closeManagementDetail">CERRAR</button></div><div class="rights-inline">${(d.derechos||[]).map(x=>`<span class="right-chip">${esc(x.derecho)} · ${x.movimientos}</span>`).join('')}</div><div class="tablewrap"><table><thead><tr><th>Fecha</th><th>Derecho</th><th>Movimiento</th><th>Operación</th></tr></thead><tbody>${(m.rows||[]).map(x=>`<tr><td>${esc(x.fecha||'—')}</td><td>${esc(x.derecho||'—')}</td><td>${esc(movementLabel(x))}</td><td>${esc(x.operacion||'—')}</td></tr>`).join('')}</tbody></table></div>`;$('closeManagementDetail').onclick=()=>$('managementDetail').classList.add('hidden')}catch(e){toast(e.message)}}
async function returnManagementCase(id){if(!confirm('¿Regresar este expediente a Información SENDA para una nueva revisión?'))return;try{await api(`/api/cases/${id}/return`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({note:'Regresado desde Gestión'})});toast('Expediente regresado a Información SENDA');await loadManagement();await loadInformation(true);await loadDashboard()}catch(e){toast(e.message)}}

// ---------- events ----------
$('importButton').onclick=importFiles;$('refreshDashboard').onclick=loadDashboard;$('applyFilters').onclick=async()=>{await loadDashboard();if(state.module==='informacion')loadInformation(true);if(state.module==='control'&&state.control.selectedId)loadControlMovements()};
$('manualCaseCreate').onclick=createManualCase;$('infoSearchBtn').onclick=()=>loadInformation(true);$('infoPageSize').onchange=()=>loadInformation(true);$('infoPrev').onclick=()=>{state.info.offset=Math.max(0,state.info.offset-state.info.pageSize);loadInformation()};$('infoNext').onclick=()=>{state.info.offset+=state.info.pageSize;loadInformation()};$('infoToControl').onclick=passSelectedToControl;
$('infoSelectPage').onchange=e=>{state.info.rows.forEach(x=>{const key=`${x.folio||''}|${x.plano||''}`;if(e.target.checked)state.info.selected.set(key,{folio:x.folio||'',plano:x.plano||''});else state.info.selected.delete(key)});updateInfoSelection()};
$('infoRows').addEventListener('change',e=>{const cb=e.target.closest('input[type=checkbox][data-key]');if(!cb)return;if(cb.checked)state.info.selected.set(cb.dataset.key,{folio:cb.dataset.folio,plano:cb.dataset.plano});else state.info.selected.delete(cb.dataset.key);updateInfoSelection()});
$('infoRows').addEventListener('click',e=>{const b=e.target.closest('.info-view');if(b)openInformationEntity(b.dataset.folio,b.dataset.plano)});
qsa('[data-info-type]').forEach(b=>b.onclick=()=>{state.info.type=b.dataset.infoType;qsa('[data-info-type]').forEach(x=>x.classList.toggle('active',x===b));loadInformation(true)});
$('controlRefresh').onclick=loadControl;$('controlSave').onclick=saveControlCase;$('controlFinalize').onclick=finalizeControlCase;$('controlPageSize').onchange=()=>{state.control.offset=0;loadControlMovements()};$('controlPrev').onclick=()=>{state.control.offset=Math.max(0,state.control.offset-state.control.pageSize);loadControlMovements()};$('controlNext').onclick=()=>{state.control.offset+=state.control.pageSize;loadControlMovements()};qsa('[data-control-type]').forEach(b=>b.onclick=()=>{state.control.type=b.dataset.controlType;state.control.offset=0;qsa('[data-control-type]').forEach(x=>x.classList.toggle('active',x===b));loadControlMovements()});
$('managementRefresh').onclick=loadManagement;
qsa('[data-export]').forEach(b=>b.onclick=()=>{if(isGitHubPages)return toast(apiUnavailableMessage());location.href='/api/export/'+b.dataset.export+'?'+query(filters())});

health();loadDashboard();
