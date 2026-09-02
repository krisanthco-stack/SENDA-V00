const $=id=>document.getElementById(id);const qsa=s=>[...document.querySelectorAll(s)];
const state={health:null,rows:[]};
const isGitHubPages=location.hostname.endsWith('github.io');
function toast(msg){let e=$('toast');e.textContent=msg;e.classList.add('show');setTimeout(()=>e.classList.remove('show'),3200)}
function filters(){return {year:$('filterYear').value,quarter:$('filterQuarter').value,month:$('filterMonth').value,district:$('filterDistrict').value,alarm:$('filterAlarm').value}}
function query(obj){let p=new URLSearchParams;Object.entries(obj).forEach(([k,v])=>{if(v&&!['TODOS','TODAS'].includes(v))p.set(k,v)});return p.toString()}
function apiUnavailableMessage(){return 'Esta vista no está conectada al servidor local de SENDA. Abra INICIAR_SENDA_V0.bat y use http://127.0.0.1:8765.'}
async function api(path,options){
  if(isGitHubPages)throw new Error(apiUnavailableMessage());
  let r=await fetch(path,options);
  let contentType=(r.headers.get('content-type')||'').toLowerCase();
  let text=await r.text();
  if(!contentType.includes('application/json')){
    let looksHtml=/^\s*<!doctype|^\s*<html|^\s*</i.test(text);
    if(looksHtml)throw new Error(`El servidor devolvió una página HTML en lugar de datos JSON (${path}). Verifique que SENDA esté abierta desde http://127.0.0.1:8765.`);
    throw new Error(`Respuesta no válida del servidor (${path}) · HTTP ${r.status}`);
  }
  let j;
  try{j=text?JSON.parse(text):{}}catch(e){throw new Error(`Respuesta JSON dañada del servidor (${path}).`)}
  if(!r.ok||j.ok===false)throw new Error(j.error||`HTTP ${r.status}`);
  return j
}
function moduleView(name){qsa('.nav').forEach(b=>b.classList.toggle('active',b.dataset.module===name));qsa('.view').forEach(v=>v.classList.toggle('active',v.dataset.view===name));if(name==='control')loadControl();if(name==='expedientes')loadCases()}
qsa('.nav').forEach(b=>b.onclick=()=>moduleView(b.dataset.module));
async function health(){if(isGitHubPages){$('serverDot').className='dot';$('serverState').textContent='Vista web';$('serverDetail').textContent='Abra INICIAR_SENDA_V0.bat para conectar datos';$('dataPath').textContent='La vista GitHub Pages no ejecuta el servidor Python local.';return}try{let h=await api('/api/health');state.health=h;$('serverDot').className='dot ok';$('serverState').textContent='Servidor conectado';$('serverDetail').textContent=h.version;$('dataPath').textContent=h.data_dir||'—'}catch(e){$('serverDot').className='dot bad';$('serverState').textContent='Servidor no disponible';$('serverDetail').textContent=e.message}}
function barChart(id,data){let box=$(id),entries=Object.entries(data||{}).sort((a,b)=>b[1]-a[1]);let max=Math.max(1,...entries.map(x=>x[1]));box.innerHTML=entries.length?entries.map(([k,v])=>`<div class="bar"><i style="height:${Math.max(4,Math.round(v/max*120))}px"></i><b>${Number(v).toLocaleString('es-CR')}</b><small title="${k}">${k}</small></div>`).join(''):'<small>Sin datos para el filtro.</small>'}
function alarmPill(a){return `<span class="pill ${a}">${a==='red'?'🔴 Roja':a==='yellow'?'🟡 Amarilla':'🟢 Verde'}</span>`}
async function loadDashboard(){try{let f=filters(),qs=query(f),d=await api('/api/dashboard?'+qs),m=await api('/api/movements?limit=80&'+qs);$('kMov').textContent=d.movimientos.toLocaleString('es-CR');$('kFolios').textContent=d.folios.toLocaleString('es-CR');$('kRed').textContent=d.alarmas.red||0;$('kYellow').textContent=d.alarmas.yellow||0;$('kDistricts').textContent=Object.keys(d.por_distrito||{}).length;$('ctxPending').textContent=d.folios;$('ctxRed').textContent=d.alarmas.red||0;$('ctxYellow').textContent=d.alarmas.yellow||0;$('ctxGreen').textContent=d.alarmas.green||0;$('ctxYear').textContent=f.year;$('ctxQuarter').textContent=f.quarter;$('ctxMonth').textContent=f.month;$('ctxDistrict').textContent=f.district;$('dashboardScope').textContent=[f.year,f.quarter,f.month,f.district,f.alarm].join(' · ');barChart('districtBars',d.por_distrito);barChart('sourceBars',d.por_fuente);state.rows=m.rows;$('recentRows').innerHTML=m.rows.slice(0,30).map(r=>`<tr><td><b>${r.folio||'—'}</b></td><td>${r.distrito}</td><td>${r.fecha||'—'}</td><td>${r.fuente}</td><td>${r.codigo||'—'}</td><td>${r.operacion||'—'}</td><td>${alarmPill(r.alarma)}</td></tr>`).join('');await loadImports()}catch(e){toast(e.message)}}
async function loadImports(){try{let r=await api('/api/imports');let by={};r.rows.forEach(x=>{let y=x.anio||'—';(by[y]??=new Set).add(x.trimestre)});$('quarterHistory').innerHTML=Object.entries(by).slice(0,4).map(([y,s])=>`<div><b>${y}</b> · ${['T1','T2','T3','T4'].map(q=>s.has(q)?q+' ✓':q+' ○').join(' · ')}</div>`).join('')||'Sin cargas registradas.'}catch(e){$('quarterHistory').textContent='Sin historial.'}}
async function loadControl(){try{let r=await api('/api/movements?limit=500&'+query(filters())),term=$('controlSearch').value.toLowerCase();let rows=r.rows.filter(x=>!term||[x.folio,x.titular,x.cedula,x.codigo,x.operacion].some(v=>String(v||'').toLowerCase().includes(term)));$('controlRows').innerHTML=rows.map(x=>`<tr><td><b>${x.folio||'—'}</b></td><td>${x.derecho||'—'}</td><td>${x.plano||'—'}</td><td>${x.fecha||'—'}</td><td>${x.distrito}</td><td>${x.codigo||'—'}</td><td>${x.operacion||'—'}</td><td>${x.titular||'—'}</td><td>${alarmPill(x.alarma)}</td></tr>`).join('')}catch(e){toast(e.message)}}
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function lastImportId(){try{let r=await api('/api/imports?limit=1');return Number(r.rows?.[0]?.id||0)}catch(e){return 0}}
async function recoverUpload(file,year,quarter,district,beforeId){
  $('importStatus').textContent=`${file.name} fue enviado. Verificando el resultado en SENDA…`;
  let offline=0;
  for(let attempt=0;;attempt++){
    try{
      await api('/api/health');offline=0;
      let r=await api('/api/imports?limit=50');
      let row=(r.rows||[]).find(x=>Number(x.id||0)>beforeId&&Number(x.anio||0)===Number(year)&&String(x.trimestre||'')===String(quarter)&&String(x.source_name||'').split(', ').includes(file.name));
      if(row){
        if(row.status==='COMPLETED')return {ok:true,inserted:Number(row.records||0),skipped:Number(row.skipped||0),errors:Number(row.errors||0),import_id:row.id,recovered:true};
        if(row.status==='FAILED')throw new Error(`La importación falló en el servidor: ${file.name}`);
        $('importStatus').textContent=`Procesando ${file.name}… servidor conectado`;
      }else $('importStatus').textContent=`Esperando confirmación de ${file.name}… servidor conectado`;
    }catch(e){
      if(String(e.message||'').startsWith('La importación falló'))throw e;
      offline++;
      if(offline>=10)throw new Error('Servidor local no disponible. Ejecute INICIAR_SENDA_V0.bat y vuelva a intentar.');
    }
    await sleep(1000);
  }
}
async function uploadOne(file,year,quarter,district,index,total){
  let beforeId=await lastImportId();
  return new Promise((resolve,reject)=>{
    let x=new XMLHttpRequest,url=`/api/upload?${query({year,quarter,district})}`,uploadComplete=false,recovering=false;
    x.open('POST',url);x.timeout=0;
    x.setRequestHeader('Content-Type','application/octet-stream');x.setRequestHeader('X-Filename',file.name);
    x.upload.onprogress=e=>{if(e.lengthComputable){let overall=((index+e.loaded/e.total)/total)*100;$('uploadProgress').style.width=overall+'%';$('importStatus').textContent=`Subiendo ${file.name} · ${Math.round(e.loaded/e.total*100)}%`}};
    x.upload.onload=()=>{uploadComplete=true;$('importStatus').textContent=`${file.name} recibido · procesando en SENDA…`};
    const recover=()=>{if(recovering)return;recovering=true;if(!uploadComplete)return reject(new Error(`La transferencia de ${file.name} se interrumpió antes de completarse.`));recoverUpload(file,year,quarter,district,beforeId).then(resolve,reject)};
    x.onload=()=>{let j;try{j=JSON.parse(x.responseText)}catch(e){return recover()}if(x.status>=400||j.ok===false)return reject(new Error(j.error||`HTTP ${x.status}`));resolve(j)};
    x.onerror=recover;x.onabort=recover;
    x.send(file);
  })
}
async function importFiles(){
  if(isGitHubPages){$('importStatus').textContent='La importación requiere SENDA local. Abra INICIAR_SENDA_V0.bat y use la ventana http://127.0.0.1:8765.';return toast('Importación disponible únicamente con el servidor local.');}
  let files=[...$('importFiles').files];if(!files.length)return toast('Seleccione uno o más archivos.');
  try{await api('/api/health')}catch(e){$('importStatus').textContent='ERROR · Servidor local no disponible. Ejecute INICIAR_SENDA_V0.bat.';return toast('Servidor local no disponible.');}
  files.sort((a,b)=>(!a.name.toUpperCase().includes('CATALOGO_COD_'))-(!b.name.toUpperCase().includes('CATALOGO_COD_')));let y=$('importYear').value,q=$('importQuarter').value,d=$('importDistrict').value,total=0;
  try{for(let i=0;i<files.length;i++){let r=await uploadOne(files[i],y,q,d,i,files.length);total+=r.inserted||0}$('uploadProgress').style.width='100%';$('importStatus').textContent=`Carga completada · ${total.toLocaleString('es-CR')} registros nuevos`;toast('Importación completada');await loadDashboard()}catch(e){$('importStatus').textContent='ERROR · '+e.message;toast(e.message)}
}
async function loadCases(){try{let r=await api('/api/cases?search='+encodeURIComponent($('caseSearch').value));$('caseList').innerHTML=r.rows.map(c=>`<article class="panel case"><b>${c.folio||'Sin folio'}</b><div>${c.distrito}</div><small>${c.status}</small><p>${c.note||'Sin nota'}</p></article>`).join('')||'<article class="panel">Sin expedientes.</article>'}catch(e){toast(e.message)}}
async function createCase(){
  if(isGitHubPages)return toast(apiUnavailableMessage());
  let body={folio:$('caseFolio').value,district:$('caseDistrict').value,note:$('caseNote').value};
  try{
    await api('/api/cases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    $('caseFolio').value='';$('caseNote').value='';loadCases();
  }catch(e){toast(e.message)}
}
function doExport(kind){if(isGitHubPages)return toast(apiUnavailableMessage());location.href='/api/export/'+kind+'?'+query(filters())}
$('applyFilters').onclick=loadDashboard;$('refreshDashboard').onclick=loadDashboard;$('controlRefresh').onclick=loadControl;$('importButton').onclick=importFiles;$('caseSearchBtn').onclick=loadCases;$('caseCreate').onclick=createCase;$('healthBtn').onclick=health;qsa('[data-export]').forEach(b=>b.onclick=()=>doExport(b.dataset.export));
health();if(!isGitHubPages)loadDashboard();
