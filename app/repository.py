from __future__ import annotations
import sqlite3, json
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from .domain import parse_date, quarter_for_month, normalize_district, alarm_level

SCHEMA='''
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS movements(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 folio TEXT, derecho TEXT, plano TEXT, fecha TEXT, codigo TEXT, operacion TEXT,
 tipo TEXT, fuente TEXT, cedula TEXT, titular TEXT,
 anio INTEGER, mes INTEGER, trimestre TEXT, distrito TEXT,
 archivo_origen TEXT, import_id INTEGER, raw_json TEXT,
 UNIQUE(folio, derecho, plano, fecha, codigo, fuente, distrito, archivo_origen)
);
CREATE INDEX IF NOT EXISTS ix_mov_period ON movements(anio,trimestre,mes,distrito);
CREATE INDEX IF NOT EXISTS ix_mov_folio ON movements(folio);
CREATE INDEX IF NOT EXISTS ix_mov_fecha ON movements(fecha);
CREATE TABLE IF NOT EXISTS imports(
 id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 anio INTEGER, trimestre TEXT, distrito TEXT, source_name TEXT, source_hash TEXT,
 records INTEGER DEFAULT 0, skipped INTEGER DEFAULT 0, errors INTEGER DEFAULT 0, status TEXT DEFAULT 'PROCESSING'
);
CREATE TABLE IF NOT EXISTS catalogs(
 kind TEXT NOT NULL, code TEXT NOT NULL, class_code TEXT NOT NULL DEFAULT '', description TEXT,
 source_file TEXT, PRIMARY KEY(kind,code,class_code)
);
CREATE TABLE IF NOT EXISTS case_files(
 id INTEGER PRIMARY KEY AUTOINCREMENT, folio TEXT, distrito TEXT, status TEXT DEFAULT 'PENDIENTE',
 note TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS case_attachments(
 id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER NOT NULL, filename TEXT, stored_path TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(case_id) REFERENCES case_files(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
'''

class Repository:
    def __init__(self, path: str|Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._init()
    def connect(self):
        c=sqlite3.connect(self.path); c.row_factory=sqlite3.Row; return c
    @contextmanager
    def connection(self):
        c=self.connect()
        try:
            with c: yield c
        finally:
            c.close()
    def _init(self):
        with self.connection() as c: c.executescript(SCHEMA)
    def create_import(self, *, year=None, quarter=None, district='', source_name='', source_hash='') -> int:
        with self.connection() as c:
            cur=c.execute('INSERT INTO imports(anio,trimestre,distrito,source_name,source_hash) VALUES(?,?,?,?,?)',(year,quarter,normalize_district(district),source_name,source_hash)); return cur.lastrowid
    def finish_import(self, import_id:int, records:int, skipped:int=0, errors:int=0, status='COMPLETED'):
        with self.connection() as c:c.execute('UPDATE imports SET records=?,skipped=?,errors=?,status=? WHERE id=?',(records,skipped,errors,status,import_id))
    def insert_movements(self, rows, import_id:int, batch_size:int=1000):
        sql='''INSERT OR IGNORE INTO movements(folio,derecho,plano,fecha,codigo,operacion,tipo,fuente,cedula,titular,anio,mes,trimestre,distrito,archivo_origen,import_id,raw_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
        batch=[]; inserted=0
        with self.connection() as c:
            for r in rows:
                d=parse_date(r.get('fecha')); year=int(r.get('anio') or (d.year if d else date.today().year)); month=int(r.get('mes') or (d.month if d else 0) or 0); q=str(r.get('trimestre') or (quarter_for_month(month) if month else ''))
                vals=(str(r.get('folio') or ''),str(r.get('derecho') or ''),str(r.get('plano') or ''),d.isoformat() if d else '',str(r.get('codigo') or ''),str(r.get('operacion') or ''),str(r.get('tipo') or ''),str(r.get('fuente') or ''),str(r.get('cedula') or ''),str(r.get('titular') or ''),year,month,q,normalize_district(r.get('distrito')),str(r.get('archivo_origen') or ''),import_id,json.dumps(r,ensure_ascii=False,default=str))
                batch.append(vals)
                if len(batch)>=batch_size:
                    before=c.total_changes; c.executemany(sql,batch); inserted+=c.total_changes-before; batch.clear()
            if batch:
                before=c.total_changes; c.executemany(sql,batch); inserted+=c.total_changes-before
        return inserted
    def _where(self, filters):
        clauses=[]; args=[]
        mapping={'year':('anio',int),'quarter':('trimestre',str),'month':('mes',int),'district':('distrito',normalize_district),'source':('fuente',str)}
        for key,(col,conv) in mapping.items():
            val=(filters or {}).get(key)
            if val not in (None,'','ALL','TODOS','Todas','TODAS'):
                clauses.append(f'{col}=?'); args.append(conv(val))
        return (' WHERE '+' AND '.join(clauses)) if clauses else '',args
    def list_movements(self, filters=None, limit=1000, offset=0):
        filters=filters or {}; where,args=self._where(filters)
        alarm=str(filters.get('alarm') or '').lower()
        cutoff90=(date.today()-__import__('datetime').timedelta(days=90)).isoformat()
        cutoff60=(date.today()-__import__('datetime').timedelta(days=60)).isoformat()
        condition='1=1'; extra=[]
        if alarm=='red': condition='latest_date IS NOT NULL AND latest_date<=?'; extra=[cutoff90]
        elif alarm=='yellow': condition='latest_date>? AND latest_date<?'; extra=[cutoff90,cutoff60]
        elif alarm=='green': condition='latest_date IS NULL OR latest_date>=?'; extra=[cutoff60]
        sql=f'''WITH filtered AS (
            SELECT movements.*, MAX(NULLIF(fecha,'')) OVER (PARTITION BY folio) AS latest_date
            FROM movements{where}
        ) SELECT * FROM filtered WHERE {condition} ORDER BY fecha DESC,id DESC LIMIT ? OFFSET ?'''
        with self.connection() as c: rows=[dict(r) for r in c.execute(sql,(*args,*extra,int(limit),int(offset)))]
        for r in rows:
            r['alarma']=alarm_level(parse_date(r.pop('latest_date',None)))
        return rows
    def dashboard(self, filters=None):
        filters=filters or {}
        where,args=self._where(filters)
        alarm=str(filters.get('alarm') or '').lower()
        cutoff90=(date.today()-__import__('datetime').timedelta(days=90)).isoformat()
        cutoff60=(date.today()-__import__('datetime').timedelta(days=60)).isoformat()
        condition='1=1'; extra=[]
        if alarm=='red': condition='latest_date IS NOT NULL AND latest_date<=?'; extra=[cutoff90]
        elif alarm=='yellow': condition='latest_date>? AND latest_date<?'; extra=[cutoff90,cutoff60]
        elif alarm=='green': condition='latest_date IS NULL OR latest_date>=?'; extra=[cutoff60]
        cte=(
            "WITH filtered AS ("
            " SELECT movements.*, MAX(NULLIF(fecha,'')) OVER (PARTITION BY folio) AS latest_date"
            f" FROM movements{where}"
            "), selected AS ("
            f" SELECT * FROM filtered WHERE {condition}"
            ") "
        )
        params=(*args,*extra)
        with self.connection() as c:
            summary=c.execute(cte+"SELECT COUNT(*) movimientos, COUNT(DISTINCT NULLIF(folio,'')) folios FROM selected",params).fetchone()
            by_source={r['fuente']:r['n'] for r in c.execute(cte+"SELECT fuente,COUNT(*) n FROM selected GROUP BY fuente ORDER BY n DESC",params)}
            by_district={r['distrito']:r['n'] for r in c.execute(cte+"SELECT distrito,COUNT(*) n FROM selected GROUP BY distrito ORDER BY n DESC",params)}
            alarm_sql=cte+"""SELECT CASE
                WHEN latest_date IS NULL OR latest_date>=? THEN 'green'
                WHEN latest_date<=? THEN 'red'
                ELSE 'yellow'
                END level, COUNT(DISTINCT folio) n
                FROM selected WHERE NULLIF(folio,'') IS NOT NULL GROUP BY level"""
            alarms={'red':0,'yellow':0,'green':0}
            for r in c.execute(alarm_sql,(*params,cutoff60,cutoff90)):
                alarms[r['level']]=r['n']
        return {'movimientos':summary['movimientos'],'folios':summary['folios'],'alarmas':alarms,'por_fuente':by_source,'por_distrito':by_district}
    def upsert_catalog(self, kind, code, class_code, description, source_file=''):
        with self.connection() as c:c.execute('INSERT INTO catalogs(kind,code,class_code,description,source_file) VALUES(?,?,?,?,?) ON CONFLICT(kind,code,class_code) DO UPDATE SET description=excluded.description,source_file=excluded.source_file',(kind,code,class_code,description,source_file))
    def catalogs(self):
        with self.connection() as c:return [dict(r) for r in c.execute('SELECT * FROM catalogs ORDER BY kind,code,class_code')]
    def list_imports(self, limit=100):
        with self.connection() as c:
            return [dict(r) for r in c.execute('SELECT * FROM imports ORDER BY id DESC LIMIT ?', (int(limit),))]
    def create_case(self, folio, district, note='', status='PENDIENTE'):
        status=str(status or 'PENDIENTE').upper()
        if status not in ('PENDIENTE','EN REVISION','FINALIZADO','REGRESADO'): status='PENDIENTE'
        with self.connection() as c:
            cur=c.execute('INSERT INTO case_files(folio,distrito,status,note) VALUES(?,?,?,?)',(str(folio or ''),normalize_district(district),status,str(note or '')))
            return cur.lastrowid
    def list_cases(self, search='', limit=200):
        q=f'%{str(search or "").strip()}%'
        with self.connection() as c:
            return [dict(r) for r in c.execute('SELECT * FROM case_files WHERE folio LIKE ? OR note LIKE ? OR distrito LIKE ? ORDER BY updated_at DESC,id DESC LIMIT ?',(q,q,q,int(limit)))]
    def add_case_attachment(self, case_id:int, filename:str, stored_path:str):
        with self.connection() as c:
            cur=c.execute('INSERT INTO case_attachments(case_id,filename,stored_path) VALUES(?,?,?)',(int(case_id),filename,stored_path));return cur.lastrowid
    def list_case_attachments(self, case_id:int):
        with self.connection() as c:return [dict(r) for r in c.execute('SELECT * FROM case_attachments WHERE case_id=? ORDER BY id DESC',(int(case_id),))]
