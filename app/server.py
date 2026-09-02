from __future__ import annotations
import json, mimetypes, os, re, tempfile, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse, unquote

from . import __version__
from .config import ensure_data_dirs
from .repository import Repository
from .importers.engine import ImportEngine
from .services.exports import export_json, export_csv, export_xlsx

class SendaApp:
    def __init__(self,data_dir,ui_dir):
        self.root,self.dirs=ensure_data_dirs(Path(data_dir))
        self.ui_dir=Path(ui_dir)
        self.repo=Repository(self.dirs['database']/'senda_v0.sqlite')
        self.importer=ImportEngine(self.repo)

def _filters(qs):
    def one(k,default=''):return qs.get(k,[default])[0]
    return {'year':one('year'),'quarter':one('quarter'),'month':one('month'),'district':one('district'),'alarm':one('alarm'),'source':one('source')}

def make_handler(app:SendaApp):
    class Handler(BaseHTTPRequestHandler):
        server_version='SENDA.V0'
        def log_message(self,fmt,*args):
            print('[SENDA.V0] '+fmt%args)
        def _json(self,payload,status=200):
            raw=json.dumps(payload,ensure_ascii=False,default=str).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def _error(self,e,status=500):
            self._json({'ok':False,'error':str(e),'type':type(e).__name__},status)
        def _send_path(self,path:Path,content_type=None,download_name=None):
            size=path.stat().st_size; self.send_response(200);self.send_header('Content-Type',content_type or mimetypes.guess_type(path.name)[0] or 'application/octet-stream');self.send_header('Content-Length',str(size))
            if download_name:self.send_header('Content-Disposition',f'attachment; filename="{download_name}"')
            self.end_headers()
            with path.open('rb') as f:
                while True:
                    chunk=f.read(1024*1024)
                    if not chunk:break
                    self.wfile.write(chunk)
        def do_GET(self):
            try:
                u=urlparse(self.path);qs=parse_qs(u.query);path=u.path
                if path=='/api/health':return self._json({'ok':True,'version':'SENDA.V0','engine_version':__version__,'data_dir':str(app.root)})
                if path=='/api/dashboard':return self._json(app.repo.dashboard(_filters(qs)))
                if path=='/api/movements':
                    limit=min(max(int(qs.get('limit',['200'])[0]),1),5000);offset=max(int(qs.get('offset',['0'])[0]),0)
                    return self._json({'ok':True,'rows':app.repo.list_movements(_filters(qs),limit=limit,offset=offset),'limit':limit,'offset':offset})
                if path=='/api/catalogs':return self._json({'ok':True,'rows':app.repo.catalogs()})
                if path=='/api/imports':return self._json({'ok':True,'rows':app.repo.list_imports(min(max(int(qs.get('limit',['100'])[0]),1),1000))})
                if path=='/api/cases':return self._json({'ok':True,'rows':app.repo.list_cases(qs.get('search',[''])[0],min(max(int(qs.get('limit',['200'])[0]),1),1000))})
                if path.startswith('/api/export/'):
                    kind=path.rsplit('/',1)[-1]; filters=_filters(qs)
                    ext={'json':'json','csv':'csv','xlsx':'xlsx'}.get(kind)
                    if not ext:return self._json({'ok':False,'error':'Formato de exportación inválido'},400)
                    target=app.dirs['exports']/f'SENDA_V0_export.{ext}'
                    if kind=='json':export_json(app.repo,filters,target);ctype='application/json'
                    elif kind=='csv':export_csv(app.repo,filters,target);ctype='text/csv; charset=utf-8'
                    else:export_xlsx(app.repo,filters,target);ctype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    return self._send_path(target,ctype,target.name)
                # static
                rel='index.html' if path in ('','/') else unquote(path.lstrip('/'))
                candidate=(app.ui_dir/rel).resolve()
                if not str(candidate).startswith(str(app.ui_dir.resolve())) or not candidate.is_file():return self._json({'ok':False,'error':'No encontrado'},404)
                return self._send_path(candidate)
            except Exception as e:
                traceback.print_exc(); return self._error(e)
        def do_POST(self):
            try:
                u=urlparse(self.path);qs=parse_qs(u.query)
                if u.path=='/api/cases':
                    length=int(self.headers.get('Content-Length') or '0')
                    if length<=0 or length>1024*1024:return self._json({'ok':False,'error':'Solicitud de expediente inválida'},400)
                    payload=json.loads(self.rfile.read(length).decode('utf-8'))
                    case_id=app.repo.create_case(payload.get('folio',''),payload.get('district',''),payload.get('note',''),payload.get('status','PENDIENTE'))
                    return self._json({'ok':True,'id':case_id},201)
                if u.path!='/api/upload':return self._json({'ok':False,'error':'No encontrado'},404)
                length=int(self.headers.get('Content-Length') or '0')
                if length<=0:return self._json({'ok':False,'error':'Archivo vacío o Content-Length ausente'},400)
                filename=Path(self.headers.get('X-Filename') or qs.get('filename',['archivo.bin'])[0]).name
                filename=re.sub(r'[^A-Za-z0-9_.() -]+','_',filename) or 'archivo.bin'
                year=int(qs.get('year',['0'])[0] or 0);quarter=qs.get('quarter',[''])[0];district=qs.get('district',[''])[0]
                if year<2000 or year>2100:return self._json({'ok':False,'error':'Año inválido'},400)
                temp_dir=Path(tempfile.mkdtemp(prefix='senda_v0_upload_',dir=app.dirs['tmp']))
                temp=temp_dir/filename
                remaining=length
                try:
                    with temp.open('wb') as f:
                        while remaining:
                            chunk=self.rfile.read(min(1024*1024,remaining))
                            if not chunk:raise ConnectionError('Carga interrumpida antes de completar el archivo')
                            f.write(chunk);remaining-=len(chunk)
                    result=app.importer.import_paths([temp],year=year,quarter=quarter,district=district)
                    result['ok']=True;result['filename']=filename;return self._json(result)
                finally:
                    import shutil
                    try:shutil.rmtree(temp_dir,ignore_errors=True)
                    except Exception:pass
            except ValueError as e:return self._error(e,400)
            except Exception as e:
                traceback.print_exc();return self._error(e,500)
    return Handler

def create_server(host='127.0.0.1',port=8765,*,data_dir=None,ui_dir=None):
    base=Path(__file__).resolve().parents[1]
    app=SendaApp(data_dir or (base/'SENDA_DATA'),ui_dir or (base/'ui'))
    server=ThreadingHTTPServer((host,int(port)),make_handler(app));server.senda_app=app
    return server

def main():
    import argparse, webbrowser
    p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=int(os.environ.get('SENDA_PORT','8765')));p.add_argument('--data-dir',default=None);p.add_argument('--no-browser',action='store_true');args=p.parse_args()
    server=create_server(args.host,args.port,data_dir=args.data_dir)
    print(f'SENDA.V0 servidor activo en http://{args.host}:{server.server_address[1]}')
    if not args.no_browser:
        try:webbrowser.open(f'http://{args.host}:{server.server_address[1]}')
        except Exception:pass
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
