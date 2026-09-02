from __future__ import annotations
import hashlib, json, sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from .domain import parse_date, quarter_for_month, normalize_district, alarm_level
from .importers.engine import movement_category

CATEGORIES=('FINCAS','HIPOTECAS','GRAVÁMENES','SEGREGACIONES','ANOTACIONES','HISTÓRICOS','CERRADAS','OTROS')
PAGE_SIZES=(25,50,100)
CASE_STATUSES=('INFORMACION','EN CONTROL','GESTION')

SCHEMA='''
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS movements(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 folio TEXT, derecho TEXT, plano TEXT, fecha TEXT, codigo TEXT, operacion TEXT,
 tipo TEXT, fuente TEXT, categoria TEXT, cedula TEXT, titular TEXT,
 anio INTEGER, mes INTEGER, trimestre TEXT, distrito TEXT,
 archivo_origen TEXT, import_id INTEGER, raw_json TEXT,
 UNIQUE(folio, derecho, plano, fecha, codigo, fuente, distrito, archivo_origen)
);
CREATE INDEX IF NOT EXISTS ix_mov_period ON movements(anio,trimestre,mes,distrito);
CREATE INDEX IF NOT EXISTS ix_mov_folio ON movements(folio);
CREATE INDEX IF NOT EXISTS ix_mov_plano ON movements(plano);
CREATE INDEX IF NOT EXISTS ix_mov_fecha ON movements(fecha);
CREATE TABLE IF NOT EXISTS imports(
 id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 anio INTEGER, trimestre TEXT, distrito TEXT, source_name TEXT, source_hash TEXT,
 records INTEGER DEFAULT 0, skipped INTEGER DEFAULT 0, errors INTEGER DEFAULT 0, status TEXT DEFAULT 'PROCESSING'
);
CREATE INDEX IF NOT EXISTS ix_import_hash_status ON imports(source_hash,status);
CREATE TABLE IF NOT EXISTS movement_signatures(
 signature TEXT PRIMARY KEY, movement_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS catalogs(
 kind TEXT NOT NULL, code TEXT NOT NULL, class_code TEXT NOT NULL DEFAULT '', description TEXT,
 source_file TEXT, PRIMARY KEY(kind,code,class_code)
);
CREATE TABLE IF NOT EXISTS case_files(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 folio TEXT, plano TEXT, distrito TEXT,
 status TEXT DEFAULT 'INFORMACION', responsable TEXT DEFAULT '', prioridad TEXT DEFAULT 'NORMAL',
 note TEXT, control_started_at TEXT, finalized_at TEXT, management_started_at TEXT,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_case_status ON case_files(status);
CREATE INDEX IF NOT EXISTS ix_case_folio ON case_files(folio);
CREATE TABLE IF NOT EXISTS case_audit(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 case_id INTEGER NOT NULL, action TEXT NOT NULL,
 previous_status TEXT, new_status TEXT, note TEXT, payload_json TEXT,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(case_id) REFERENCES case_files(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_case_audit_case ON case_audit(case_id,id);
CREATE TABLE IF NOT EXISTS case_attachments(
 id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER NOT NULL, filename TEXT, stored_path TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(case_id) REFERENCES case_files(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
'''


def _clean(v): return str(v or '').strip()


def _movement_signature(values):
    """Firma lógica independiente del nombre de archivo/importación.

    Evita que el mismo movimiento vuelva a insertarse si llega en un archivo
    renombrado, otro ZIP/RAR o una nueva carga del mismo corte.
    """
    payload='|'.join(_clean(v).upper() for v in values)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def _canonical_status(v):
    s=_clean(v).upper().replace('_',' ')
    return {
        'PENDIENTE':'INFORMACION','INFORMACIÓN':'INFORMACION','INFORMACION':'INFORMACION','REGRESADO':'INFORMACION',
        'EN REVISION':'EN CONTROL','EN REVISIÓN':'EN CONTROL','EN CONTROL':'EN CONTROL',
        'FINALIZADO':'GESTION','GESTIÓN':'GESTION','GESTION':'GESTION'
    }.get(s,'INFORMACION')


class Repository:
    def __init__(self,path:str|Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._init()

    def connect(self):
        c=sqlite3.connect(self.path); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

    @contextmanager
    def connection(self):
        c=self.connect()
        try:
            with c: yield c
        finally:c.close()

    def _init(self):
        with self.connection() as c:
            # First create every table possible on a new database.
            c.executescript(SCHEMA)
            self._migrate(c)

    def _columns(self,c,table): return {r['name'] for r in c.execute(f'PRAGMA table_info({table})')}

    def _migrate(self,c):
        # Additive migration only. Existing loaded data is never dropped/recreated.
        mov=self._columns(c,'movements')
        if 'categoria' not in mov:c.execute("ALTER TABLE movements ADD COLUMN categoria TEXT DEFAULT ''")
        cases=self._columns(c,'case_files')
        additions={
            'plano':"TEXT DEFAULT ''",'responsable':"TEXT DEFAULT ''",'prioridad':"TEXT DEFAULT 'NORMAL'",
            'control_started_at':'TEXT','finalized_at':'TEXT','management_started_at':'TEXT'
        }
        for col,typ in additions.items():
            if col not in cases:c.execute(f'ALTER TABLE case_files ADD COLUMN {col} {typ}')
        c.executescript('''
        CREATE INDEX IF NOT EXISTS ix_mov_plano ON movements(plano);
                CREATE INDEX IF NOT EXISTS ix_case_status ON case_files(status);
        CREATE INDEX IF NOT EXISTS ix_case_folio ON case_files(folio);
                CREATE TABLE IF NOT EXISTS case_audit(
         id INTEGER PRIMARY KEY AUTOINCREMENT,case_id INTEGER NOT NULL,action TEXT NOT NULL,
         previous_status TEXT,new_status TEXT,note TEXT,payload_json TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,
         FOREIGN KEY(case_id) REFERENCES case_files(id) ON DELETE CASCADE);
        CREATE INDEX IF NOT EXISTS ix_case_audit_case ON case_audit(case_id,id);
        ''')
        c.executescript('''
        CREATE INDEX IF NOT EXISTS ix_import_hash_status ON imports(source_hash,status);
        CREATE TABLE IF NOT EXISTS movement_signatures(
         signature TEXT PRIMARY KEY,movement_id INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        ''')
        # No destructive backfill: existing 0.4.0 rows stay untouched. New 0.4.1
        # imports populate exact source-row signatures from this point forward.
        # Preserve old cases while translating their workflow state.
        for old,new in (('PENDIENTE','INFORMACION'),('EN REVISION','EN CONTROL'),('FINALIZADO','GESTION'),('REGRESADO','INFORMACION')):
            c.execute('UPDATE case_files SET status=? WHERE UPPER(status)=?',(new,old))
        # Classify legacy rows in one SQL pass. New inserts use the Python classifier below.
        c.execute('''UPDATE movements SET categoria=CASE
            WHEN UPPER(COALESCE(operacion,'')||' '||COALESCE(fuente,'')) LIKE '%HIPOTECA%' THEN 'HIPOTECAS'
            WHEN UPPER(COALESCE(operacion,'')||' '||COALESCE(fuente,'')) LIKE '%SEGREG%' THEN 'SEGREGACIONES'
            WHEN UPPER(COALESCE(operacion,'')||' '||COALESCE(fuente,'')) LIKE '%ANOT%' THEN 'ANOTACIONES'
            WHEN UPPER(COALESCE(operacion,'')||' '||COALESCE(fuente,'')) LIKE '%GRAVAM%'
              OR UPPER(COALESCE(operacion,'')) LIKE '%SERVIDUM%'
              OR UPPER(COALESCE(operacion,'')) LIKE '%EMBARGO%'
              OR UPPER(COALESCE(operacion,'')) LIKE '%LIMITACION%'
              OR UPPER(COALESCE(operacion,'')) LIKE '%DEMANDA%' THEN 'GRAVÁMENES'
            WHEN UPPER(COALESCE(operacion,'')||' '||COALESCE(fuente,'')) LIKE '%CIERRE%'
              OR UPPER(COALESCE(operacion,'')||' '||COALESCE(fuente,'')) LIKE '%CERRAD%' THEN 'CERRADAS'
            WHEN UPPER(COALESCE(fuente,'')) LIKE 'FINCAS%' THEN 'FINCAS'
            WHEN UPPER(COALESCE(fuente,'')) LIKE '%HISTOR%' THEN 'HISTÓRICOS'
            ELSE 'OTROS' END
            WHERE COALESCE(categoria,'')='' ''')

    # ---------- imports / movements ----------
    def has_completed_import_hash(self,source_hash:str) -> bool:
        if not source_hash:return False
        with self.connection() as c:
            return c.execute("SELECT 1 FROM imports WHERE source_hash=? AND status='COMPLETED' LIMIT 1",(source_hash,)).fetchone() is not None

    def create_import(self,*,year=None,quarter=None,district='',source_name='',source_hash='')->int:
        with self.connection() as c:
            cur=c.execute('INSERT INTO imports(anio,trimestre,distrito,source_name,source_hash) VALUES(?,?,?,?,?)',(year,quarter,normalize_district(district),source_name,source_hash));return cur.lastrowid

    def finish_import(self,import_id:int,records:int,skipped:int=0,errors:int=0,status='COMPLETED'):
        with self.connection() as c:c.execute('UPDATE imports SET records=?,skipped=?,errors=?,status=? WHERE id=?',(records,skipped,errors,status,import_id))

    def insert_movements(self,rows,import_id:int,batch_size:int=1000):
        sql='''INSERT OR IGNORE INTO movements(folio,derecho,plano,fecha,codigo,operacion,tipo,fuente,categoria,cedula,titular,anio,mes,trimestre,distrito,archivo_origen,import_id,raw_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
        inserted=0;duplicates=0
        with self.connection() as c:
            for r in rows:
                d=parse_date(r.get('fecha'));year=int(r.get('anio') or (d.year if d else date.today().year));month=int(r.get('mes') or (d.month if d else 0) or 0);q=str(r.get('trimestre') or (quarter_for_month(month) if month else ''))
                op=_clean(r.get('operacion'));src=_clean(r.get('fuente') or r.get('tipo'));cat=_clean(r.get('categoria')) or movement_category(op,src)
                folio=_clean(r.get('folio'));derecho=_clean(r.get('derecho'));plano=_clean(r.get('plano'));fecha=d.isoformat() if d else '';codigo=_clean(r.get('codigo'));cedula=_clean(r.get('cedula'));titular=_clean(r.get('titular'))
                signature=_clean(r.get('_source_signature')) or _movement_signature((folio,derecho,plano,fecha,codigo,op,src,cedula,titular))
                before=c.total_changes
                c.execute('INSERT OR IGNORE INTO movement_signatures(signature) VALUES(?)',(signature,))
                if c.total_changes==before:
                    duplicates+=1
                    continue
                vals=(folio,derecho,plano,fecha,codigo,op,_clean(r.get('tipo')),src,cat,cedula,titular,year,month,q,normalize_district(r.get('distrito')),_clean(r.get('archivo_origen')),import_id,json.dumps(r,ensure_ascii=False,default=str))
                cur=c.execute(sql,vals)
                if cur.rowcount:
                    inserted+=1
                    c.execute('UPDATE movement_signatures SET movement_id=? WHERE signature=?',(cur.lastrowid,signature))
                else:
                    # Defensive rollback of the signature marker if the legacy UNIQUE
                    # constraint rejected the movement for an unexpected reason.
                    c.execute('DELETE FROM movement_signatures WHERE signature=? AND movement_id IS NULL',(signature,))
                    duplicates+=1
        self._last_insert_duplicates=duplicates
        return inserted

    @property
    def last_insert_duplicates(self):
        return int(getattr(self,'_last_insert_duplicates',0))

    def _where(self,filters,alias=''):
        filters=filters or {};p=(alias+'.') if alias else '';clauses=[];args=[]
        mapping={'year':('anio',int),'quarter':('trimestre',str),'month':('mes',int),'district':('distrito',normalize_district),'source':('fuente',str),'movement_type':('categoria',str)}
        for key,(col,conv) in mapping.items():
            val=filters.get(key)
            if val not in (None,'','ALL','TODOS','Todas','TODAS'):
                clauses.append(f'{p}{col}=?');args.append(conv(val))
        search=_clean(filters.get('search'))
        if search:
            q=f'%{search}%';clauses.append(f'({p}folio LIKE ? OR {p}plano LIKE ? OR {p}titular LIKE ? OR {p}cedula LIKE ? OR {p}operacion LIKE ?)');args.extend([q]*5)
        return (' WHERE '+' AND '.join(clauses)) if clauses else '',args

    def _alarm_filter(self,filters,last_col='latest_date'):
        alarm=_clean((filters or {}).get('alarm')).lower();cut90=(date.today()-timedelta(days=90)).isoformat();cut60=(date.today()-timedelta(days=60)).isoformat()
        if alarm=='red':return f'{last_col} IS NOT NULL AND {last_col}<=?',[cut90]
        if alarm=='yellow':return f'{last_col}>? AND {last_col}<?',[cut90,cut60]
        if alarm=='green':return f'({last_col} IS NULL OR {last_col}>=?)',[cut60]
        return '1=1',[]

    def _case_map(self):
        with self.connection() as c:rows=[dict(r) for r in c.execute('SELECT * FROM case_files ORDER BY id DESC')]
        out={}
        for r in rows:
            if r['folio']:out.setdefault(('folio',r['folio']),r)
            if r.get('plano'):out.setdefault(('plano',r['plano']),r)
        return out

    def _attach_workflow(self,rows):
        cmap=self._case_map()
        for r in rows:
            case=cmap.get(('folio',r.get('folio') or '')) or cmap.get(('plano',r.get('plano') or ''))
            r['case_id']=case['id'] if case else None;r['estado_expediente']=case['status'] if case else 'INFORMACION';r['en_control']=bool(case and case['status']=='EN CONTROL');r['en_gestion']=bool(case and case['status']=='GESTION')
        return rows

    def list_movements(self,filters=None,limit=1000,offset=0,order='desc'):
        filters=filters or {};where,args=self._where(filters);condition,extra=self._alarm_filter(filters)
        direction='ASC' if str(order).lower()=='asc' else 'DESC'
        sql=f'''WITH filtered AS (
            SELECT movements.*,MAX(NULLIF(fecha,'')) OVER (PARTITION BY COALESCE(NULLIF(folio,''),'@'||NULLIF(plano,''))) latest_date
            FROM movements{where}
        ) SELECT * FROM filtered WHERE {condition} ORDER BY CASE WHEN fecha='' THEN 1 ELSE 0 END,fecha {direction},id {direction} LIMIT ? OFFSET ?'''
        with self.connection() as c:rows=[dict(r) for r in c.execute(sql,(*args,*extra,int(limit),int(offset)))]
        for r in rows:r['alarma']=alarm_level(parse_date(r.pop('latest_date',None)))
        return self._attach_workflow(rows)

    # ---------- information / dashboard ----------
    def list_information(self,filters=None,limit=25,offset=0):
        if int(limit) not in PAGE_SIZES:raise ValueError('Tamaño de página permitido: 25, 50 o 100')
        filters=filters or {};where,args=self._where(filters,'m');condition,extra=self._alarm_filter(filters,'last_date')
        no_mov_filter=not any(filters.get(k) not in (None,'','TODOS','TODAS','ALL') for k in ('year','quarter','month','movement_type','alarm','source'))
        manual_clauses=["cf.status<>'GESTION'","NOT EXISTS(SELECT 1 FROM movements mx WHERE (cf.folio<>'' AND mx.folio=cf.folio) OR (cf.folio='' AND cf.plano<>'' AND mx.plano=cf.plano))"]
        manual_args=[]
        if not no_mov_filter:manual_clauses.append('0=1')
        q=_clean(filters.get('search'))
        if q:manual_clauses.append('(cf.folio LIKE ? OR cf.plano LIKE ? OR cf.note LIKE ? OR cf.responsable LIKE ?)');manual_args.extend([f'%{q}%']*4)
        dist=filters.get('district')
        if dist not in (None,'','TODOS','TODAS','ALL'):manual_clauses.append('cf.distrito=?');manual_args.append(normalize_district(dist))
        manual_where=' AND '.join(manual_clauses)
        cte=f'''WITH selected AS (
          SELECT m.* FROM movements m{where}
        ), grouped AS (
          SELECT COALESCE(NULLIF(folio,''),'@PLANO:'||plano) entity_key,
                 MAX(folio) folio,MAX(plano) plano,MAX(distrito) distrito,
                 MIN(NULLIF(fecha,'')) first_date,MAX(NULLIF(fecha,'')) last_date,
                 COUNT(*) movimientos,COUNT(DISTINCT NULLIF(derecho,'')) derechos,
                 SUM(categoria='FINCAS') c_fincas,SUM(categoria='HIPOTECAS') c_hipotecas,SUM(categoria='GRAVÁMENES') c_gravamenes,
                 SUM(categoria='SEGREGACIONES') c_segregaciones,SUM(categoria='ANOTACIONES') c_anotaciones,
                 SUM(categoria='HISTÓRICOS') c_historicos,SUM(categoria='CERRADAS') c_cerradas,SUM(categoria='OTROS') c_otros
          FROM selected
          WHERE COALESCE(NULLIF(folio,''),NULLIF(plano,'')) IS NOT NULL
          GROUP BY entity_key
        ), visible_mov AS (
          SELECT * FROM grouped g WHERE {condition}
          AND NOT EXISTS(SELECT 1 FROM case_files cf WHERE cf.status='GESTION' AND ((g.folio<>'' AND cf.folio=g.folio) OR (g.folio='' AND g.plano<>'' AND cf.plano=g.plano)))
        ), manual AS (
          SELECT 'MANUAL:'||cf.id entity_key,cf.folio folio,cf.plano plano,cf.distrito distrito,
                 NULL first_date,NULL last_date,0 movimientos,0 derechos,
                 0 c_fincas,0 c_hipotecas,0 c_gravamenes,0 c_segregaciones,0 c_anotaciones,0 c_historicos,0 c_cerradas,0 c_otros
          FROM case_files cf WHERE {manual_where}
        ), entities AS (
          SELECT * FROM visible_mov UNION ALL SELECT * FROM manual
        )'''
        params=(*args,*extra,*manual_args)
        with self.connection() as c:
            total=c.execute(cte+' SELECT COUNT(*) n FROM entities',params).fetchone()['n']
            rows=[dict(r) for r in c.execute(cte+''' SELECT * FROM entities
                ORDER BY CASE WHEN first_date IS NULL THEN 1 ELSE 0 END,first_date ASC,entity_key ASC LIMIT ? OFFSET ?''',(*params,int(limit),int(offset)))]
        cmap=self._case_map();out=[]
        for r in rows:
            case=cmap.get(('folio',r['folio'])) or cmap.get(('plano',r['plano']))
            cats={'FINCAS':r.pop('c_fincas'),'HIPOTECAS':r.pop('c_hipotecas'),'GRAVÁMENES':r.pop('c_gravamenes'),'SEGREGACIONES':r.pop('c_segregaciones'),'ANOTACIONES':r.pop('c_anotaciones'),'HISTÓRICOS':r.pop('c_historicos'),'CERRADAS':r.pop('c_cerradas'),'OTROS':r.pop('c_otros')}
            r['categorias']=cats;r['case_id']=case['id'] if case else None;r['status']=case['status'] if case else 'INFORMACION';r['responsable']=case.get('responsable','') if case else '';r['prioridad']=case.get('prioridad','NORMAL') if case else 'NORMAL';r['alarma']=alarm_level(parse_date(r['last_date']))
            out.append(r)
        return {'rows':out,'total':total,'limit':int(limit),'offset':int(offset)}

    def entity_movements(self,folio='',plano='',category='TODOS',limit=25,offset=0):
        if int(limit) not in PAGE_SIZES:raise ValueError('Tamaño de página permitido: 25, 50 o 100')
        folio=_clean(folio);plano=_clean(plano)
        if not folio and not plano:raise ValueError('Folio o plano requerido')
        clauses=[];args=[]
        if folio:clauses.append('folio=?');args.append(folio)
        else:clauses.append('plano=?');args.append(plano)
        if category not in (None,'','TODOS','TODAS','ALL'):clauses.append('categoria=?');args.append(category)
        where=' WHERE '+' AND '.join(clauses)
        with self.connection() as c:
            total=c.execute('SELECT COUNT(*) n FROM movements'+where,args).fetchone()['n']
            rows=[dict(r) for r in c.execute('SELECT * FROM movements'+where+" ORDER BY CASE WHEN fecha='' THEN 1 ELSE 0 END,fecha ASC,id ASC LIMIT ? OFFSET ?",(*args,int(limit),int(offset)))]
            rights=[dict(r) for r in c.execute("SELECT COALESCE(NULLIF(derecho,''),'GENERAL') derecho,COUNT(*) movimientos FROM movements"+where+" GROUP BY COALESCE(NULLIF(derecho,''),'GENERAL') ORDER BY derecho",args)]
        return {'rows':rows,'rights':rights,'total':total,'limit':int(limit),'offset':int(offset)}

    def dashboard(self,filters=None):
        filters=filters or {};where,args=self._where(filters);condition,extra=self._alarm_filter(filters)
        cte=("WITH filtered AS ( SELECT movements.*,MAX(NULLIF(fecha,'')) OVER (PARTITION BY COALESCE(NULLIF(folio,''),'@'||NULLIF(plano,''))) latest_date FROM movements"+where+
             "), selected AS ( SELECT * FROM filtered WHERE "+condition+") ")
        params=(*args,*extra);cut90=(date.today()-timedelta(days=90)).isoformat();cut60=(date.today()-timedelta(days=60)).isoformat()
        with self.connection() as c:
            summary=c.execute(cte+"SELECT COUNT(*) movimientos,COUNT(DISTINCT COALESCE(NULLIF(folio,''),'@'||NULLIF(plano,''))) folios FROM selected",params).fetchone()
            by_source={r['fuente']:r['n'] for r in c.execute(cte+'SELECT fuente,COUNT(*) n FROM selected GROUP BY fuente ORDER BY n DESC',params)}
            by_district={r['distrito']:r['n'] for r in c.execute(cte+'SELECT distrito,COUNT(*) n FROM selected GROUP BY distrito ORDER BY n DESC',params)}
            by_category={r['categoria']:r['n'] for r in c.execute(cte+'SELECT categoria,COUNT(*) n FROM selected GROUP BY categoria ORDER BY n DESC',params)}
            by_month={int(r['mes']):r['n'] for r in c.execute(cte+'SELECT mes,COUNT(*) n FROM selected WHERE mes IS NOT NULL GROUP BY mes ORDER BY mes',params)}
            recent=[dict(r) for r in c.execute(cte+'''SELECT fecha,folio,plano,categoria,codigo,operacion,distrito
                FROM selected ORDER BY CASE WHEN fecha='' THEN 1 ELSE 0 END,fecha DESC,id DESC LIMIT 12''',params)]
            tramite=c.execute(cte+'''SELECT COUNT(*) n FROM selected s WHERE EXISTS(
                SELECT 1 FROM case_files cf WHERE cf.status IN ('EN CONTROL','GESTION') AND ((cf.folio<>'' AND cf.folio=s.folio) OR (cf.folio='' AND cf.plano<>'' AND cf.plano=s.plano)))''',params).fetchone()['n']
            cases={r['status']:r['n'] for r in c.execute("SELECT status,COUNT(*) n FROM case_files GROUP BY status")}
            alarm_sql=cte+'''SELECT CASE WHEN latest_date IS NULL OR latest_date>=? THEN 'green' WHEN latest_date<=? THEN 'red' ELSE 'yellow' END level,COUNT(DISTINCT COALESCE(NULLIF(folio,''),'@'||NULLIF(plano,''))) n FROM selected GROUP BY level'''
            alarms={'red':0,'yellow':0,'green':0}
            for r in c.execute(alarm_sql,(*params,cut60,cut90)):alarms[r['level']]=r['n']
        return {'movimientos':summary['movimientos'],'folios':summary['folios'],'movimientos_tramite':tramite,'casos_control':cases.get('EN CONTROL',0),'casos_gestion':cases.get('GESTION',0),'alarmas':alarms,'por_fuente':by_source,'por_distrito':by_district,'por_categoria':by_category,'por_mes':by_month,'recientes':recent}

    # ---------- catalogs ----------
    def upsert_catalog(self,kind,code,class_code,description,source_file=''):
        with self.connection() as c:c.execute('INSERT INTO catalogs(kind,code,class_code,description,source_file) VALUES(?,?,?,?,?) ON CONFLICT(kind,code,class_code) DO UPDATE SET description=excluded.description,source_file=excluded.source_file',(kind,code,class_code,description,source_file))
    def catalogs(self):
        with self.connection() as c:return [dict(r) for r in c.execute('SELECT * FROM catalogs ORDER BY kind,code,class_code')]
    def list_imports(self,limit=100):
        with self.connection() as c:return [dict(r) for r in c.execute('SELECT * FROM imports ORDER BY id DESC LIMIT ?',(int(limit),))]

    # ---------- cases / workflow ----------
    def _find_case(self,c,folio='',plano=''):
        folio=_clean(folio);plano=_clean(plano)
        if folio:
            row=c.execute('SELECT * FROM case_files WHERE folio=? ORDER BY id DESC LIMIT 1',(folio,)).fetchone()
            if row:return dict(row)
        if plano:
            row=c.execute("SELECT * FROM case_files WHERE plano=? AND COALESCE(folio,'')='' ORDER BY id DESC LIMIT 1",(plano,)).fetchone()
            if row:return dict(row)
        return None

    def _audit(self,c,case_id,action,previous='',new='',note='',payload=None):
        c.execute('INSERT INTO case_audit(case_id,action,previous_status,new_status,note,payload_json) VALUES(?,?,?,?,?,?)',(int(case_id),action,previous,new,_clean(note),json.dumps(payload or {},ensure_ascii=False,default=str)))

    def create_case(self,folio,district,note='',status='INFORMACION',plano='',responsable='',prioridad='NORMAL'):
        folio=_clean(folio);plano=_clean(plano)
        if not folio and not plano:raise ValueError('El expediente requiere folio/finca o plano')
        status=_canonical_status(status);district=normalize_district(district);prioridad=_clean(prioridad).upper() or 'NORMAL'
        with self.connection() as c:
            existing=self._find_case(c,folio,plano)
            if existing:
                c.execute('UPDATE case_files SET plano=COALESCE(NULLIF(?,\'\'),plano),distrito=?,note=CASE WHEN ?<>\'\' THEN ? ELSE note END,responsable=CASE WHEN ?<>\'\' THEN ? ELSE responsable END,prioridad=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(plano,district,_clean(note),_clean(note),_clean(responsable),_clean(responsable),prioridad,existing['id']))
                return existing['id']
            cur=c.execute('INSERT INTO case_files(folio,plano,distrito,status,note,responsable,prioridad) VALUES(?,?,?,?,?,?,?)',(folio,plano,district,status,_clean(note),_clean(responsable),prioridad));cid=cur.lastrowid
            self._audit(c,cid,'CREAR EXPEDIENTE','',status,note,{'folio':folio,'plano':plano});return cid

    def get_case(self,case_id:int):
        with self.connection() as c:
            r=c.execute('SELECT * FROM case_files WHERE id=?',(int(case_id),)).fetchone()
            if not r:raise KeyError('Expediente no encontrado')
            return dict(r)

    def update_case(self,case_id:int,changes:dict):
        allowed=('folio','plano','distrito','responsable','prioridad','note');sets=[];args=[]
        with self.connection() as c:
            old=c.execute('SELECT * FROM case_files WHERE id=?',(int(case_id),)).fetchone()
            if not old:raise KeyError('Expediente no encontrado')
            for k in allowed:
                if k in changes:
                    val=normalize_district(changes[k]) if k=='distrito' else _clean(changes[k]);sets.append(f'{k}=?');args.append(val)
            if not sets:return dict(old)
            sets.append('updated_at=CURRENT_TIMESTAMP');c.execute('UPDATE case_files SET '+','.join(sets)+' WHERE id=?',(*args,int(case_id)))
            self._audit(c,case_id,'MODIFICAR EXPEDIENTE',old['status'],old['status'],changes.get('note',''),{k:changes[k] for k in changes if k in allowed})
        return self.get_case(case_id)

    def select_cases_for_control(self,items):
        selected=0
        with self.connection() as c:
            for item in items:
                folio=_clean(item.get('folio'));plano=_clean(item.get('plano'))
                if not folio and not plano:continue
                case=self._find_case(c,folio,plano)
                if case and case['status']=='GESTION':continue
                if not case:
                    src=c.execute('SELECT distrito,plano FROM movements WHERE (?<>\'\' AND folio=?) OR (?=\'\' AND ?<>\'\' AND plano=?) ORDER BY fecha DESC LIMIT 1',(folio,folio,folio,plano,plano)).fetchone()
                    district=(src['distrito'] if src else 'SIN IDENTIFICAR');real_plano=plano or (src['plano'] if src else '')
                    cur=c.execute("INSERT INTO case_files(folio,plano,distrito,status,control_started_at) VALUES(?,?,?,'EN CONTROL',CURRENT_TIMESTAMP)",(folio,real_plano,district));cid=cur.lastrowid;previous='INFORMACION'
                else:
                    cid=case['id'];previous=case['status'];c.execute("UPDATE case_files SET status='EN CONTROL',control_started_at=COALESCE(control_started_at,CURRENT_TIMESTAMP),updated_at=CURRENT_TIMESTAMP WHERE id=?",(cid,))
                self._audit(c,cid,'PASAR A CONTROL',previous,'EN CONTROL','',{'folio':folio,'plano':plano});selected+=1
        return selected

    def list_cases(self,search='',limit=200,status=None):
        q=f'%{_clean(search)}%';clauses=['(folio LIKE ? OR plano LIKE ? OR note LIKE ? OR distrito LIKE ? OR responsable LIKE ?)'];args=[q]*5
        if status:clauses.append('status=?');args.append(_canonical_status(status))
        sql='SELECT * FROM case_files WHERE '+' AND '.join(clauses)+' ORDER BY updated_at DESC,id DESC LIMIT ?';args.append(int(limit))
        with self.connection() as c:return [dict(r) for r in c.execute(sql,args)]

    def list_control(self,search='',limit=500):return self.list_cases(search,limit,'EN CONTROL')
    def list_management(self,search='',limit=500):return self.list_cases(search,limit,'GESTION')

    def _case_movement_where(self,case):
        if case['folio']:return 'folio=?',[case['folio']]
        if case.get('plano'):return 'plano=?',[case['plano']]
        return '1=0',[]

    def case_movements(self,case_id:int,category='TODOS',limit=25,offset=0):
        if int(limit) not in PAGE_SIZES:raise ValueError('Tamaño de página permitido: 25, 50 o 100')
        case=self.get_case(case_id);where,args=self._case_movement_where(case);clauses=[where]
        if category not in (None,'','TODOS','TODAS','ALL'):clauses.append('categoria=?');args.append(category)
        sqlwhere=' WHERE '+' AND '.join(f'({x})' for x in clauses)
        with self.connection() as c:
            total=c.execute('SELECT COUNT(*) n FROM movements'+sqlwhere,args).fetchone()['n']
            rows=[dict(r) for r in c.execute('SELECT * FROM movements'+sqlwhere+" ORDER BY CASE WHEN fecha='' THEN 1 ELSE 0 END,fecha ASC,id ASC LIMIT ? OFFSET ?",(*args,int(limit),int(offset)))]
        for r in rows:r['alarma']=alarm_level(parse_date(r.get('fecha')))
        return {'rows':rows,'total':total,'limit':int(limit),'offset':int(offset)}

    def case_detail(self,case_id:int):
        case=self.get_case(case_id);where,args=self._case_movement_where(case)
        with self.connection() as c:
            total=c.execute('SELECT COUNT(*) n FROM movements WHERE '+where,args).fetchone()['n']
            rights=[dict(r) for r in c.execute("SELECT COALESCE(NULLIF(derecho,''),'GENERAL') derecho,COUNT(*) movimientos,MIN(NULLIF(fecha,'')) primera_fecha,MAX(NULLIF(fecha,'')) ultima_fecha FROM movements WHERE "+where+" GROUP BY COALESCE(NULLIF(derecho,''),'GENERAL') ORDER BY derecho",args)]
            cats={r['categoria']:r['n'] for r in c.execute('SELECT categoria,COUNT(*) n FROM movements WHERE '+where+' GROUP BY categoria ORDER BY n DESC',args)}
        return {'case':case,'derechos':rights,'movimientos_total':total,'categorias':cats,'audit':self.case_audit(case_id)}

    def finalize_case(self,case_id:int,note=''):
        with self.connection() as c:
            old=c.execute('SELECT * FROM case_files WHERE id=?',(int(case_id),)).fetchone()
            if not old:raise KeyError('Expediente no encontrado')
            if old['status']!='EN CONTROL':raise ValueError('Solo un trámite en Control puede finalizarse')
            c.execute("UPDATE case_files SET status='GESTION',finalized_at=CURRENT_TIMESTAMP,management_started_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?",(int(case_id),))
            self._audit(c,case_id,'FINALIZAR CONTROL','EN CONTROL','GESTION',note)
        return self.get_case(case_id)

    def return_case_to_information(self,case_id:int,note=''):
        with self.connection() as c:
            old=c.execute('SELECT * FROM case_files WHERE id=?',(int(case_id),)).fetchone()
            if not old:raise KeyError('Expediente no encontrado')
            if old['status']!='GESTION':raise ValueError('Solo un trámite en Gestión puede regresar')
            c.execute("UPDATE case_files SET status='INFORMACION',control_started_at=NULL,finalized_at=NULL,management_started_at=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",(int(case_id),))
            self._audit(c,case_id,'REGRESAR A INFORMACION SENDA','GESTION','INFORMACION',note)
        return self.get_case(case_id)

    def case_audit(self,case_id:int):
        with self.connection() as c:return [dict(r) for r in c.execute('SELECT * FROM case_audit WHERE case_id=? ORDER BY id ASC',(int(case_id),))]

    def add_case_attachment(self,case_id:int,filename:str,stored_path:str):
        with self.connection() as c:
            cur=c.execute('INSERT INTO case_attachments(case_id,filename,stored_path) VALUES(?,?,?)',(int(case_id),filename,stored_path));return cur.lastrowid
    def list_case_attachments(self,case_id:int):
        with self.connection() as c:return [dict(r) for r in c.execute('SELECT * FROM case_attachments WHERE case_id=? ORDER BY id DESC',(int(case_id),))]
